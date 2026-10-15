#!/usr/bin/env python3
"""Test98 shared immutable benchmark corpus cache (local preparation, remote validation).

The official simdjson-data repository is fetched only to the user's workstation.
The resulting byte-identical ZIP is deployed over SSH to both EPCC and Cloud-V.
No corpus contents or vendor sources are committed to VectorPath.
"""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, tempfile, urllib.request, zipfile

SOURCE_URL = 'https://github.com/simdjson/simdjson-data.git'
SOURCE_COMMIT = '4197c425e857f0ec38e89822fdd0bd9ea21f4daf'
CORPUS_ID = 'simdjson-data-4197c425-test98'
FILES = (
    'apache_builds.json', 'canada.json', 'citm_catalog.json', 'github_events.json',
    'google_maps_api_compact_response.json', 'google_maps_api_response.json', 'gsoc-2018.json', 'instruments.json',
    'marine_ik.json', 'mesh.json', 'mesh.pretty.json', 'numbers.json',
    'twitter_api_compact_response.json', 'twitter_api_response.json', 'twitterescaped.json', 'twitter.json',
    'twitter_timeline.json', 'update-center.json',
)

MAX_FILE = 40*1024*1024
MAX_TOTAL = 200*1024*1024

def sha(path):
    d=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):d.update(chunk)
    return d.hexdigest()

def strict_json(data):
    def reject_constant(value):raise ValueError('Non-standard JSON constant: '+value)
    return json.loads(data,parse_constant=reject_constant)

def json_dump(obj):return (json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode('utf8')

def verify(zip_path):
    """Validate ZIP layout, CRC, hashes, full JSON syntax, pinned commit; never extract here."""
    path=pathlib.Path(zip_path)
    if not path.is_file() or path.stat().st_size>MAX_TOTAL or not path.stat().st_size:
        raise ValueError('Corpus archive absent/empty/too large')
    with zipfile.ZipFile(path) as z:
        expected=['manifest.json']+['files/'+f for f in FILES]
        if sorted(z.namelist())!=sorted(expected):raise ValueError('Unexpected corpus archive entries')
        if any(info.file_size>MAX_FILE for info in z.infolist() if info.filename!='manifest.json'):
            raise ValueError('Oversize declared corpus entry')
        if z.getinfo('manifest.json').file_size > 65536:raise ValueError('Corpus manifest too large')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('corpus_id')!=CORPUS_ID or manifest.get('upstream_commit')!=SOURCE_COMMIT or manifest.get('source_url')!=SOURCE_URL:
            raise ValueError('Unrecognized benchmark corpus provenance')
        if [x['name'] for x in manifest.get('files',[])]!=list(FILES):raise ValueError('Corpus file manifest differs from curated set')
        total=0
        for rec in manifest['files']:
            name=rec['name']; data=z.read('files/'+name)
            total+=len(data)
            if len(data)>MAX_FILE or total>MAX_TOTAL:raise ValueError('Corpus size cap exceeded')
            if len(data)!=rec['bytes'] or hashlib.sha256(data).hexdigest()!=rec['sha256']:
                raise ValueError('Corpus member hash mismatch: '+name)
            # FULL DOCUMENT JSON; NDJSON intentionally excluded from DOM test.
            strict_json(data)
        if z.testzip():raise ValueError('ZIP CRC mismatch')
    return manifest

def prepare(cache):
    path=pathlib.Path(cache).resolve(); path.mkdir(parents=True,exist_ok=True)
    dest=path/(CORPUS_ID+'.zip')
    if dest.exists():
        manifest=verify(dest)
        print(json.dumps({'archive':str(dest),'sha256':sha(dest),'files':len(manifest['files']),'cached':True}))
        return
    # Fetch only the selected fixtures from the immutable commit. No huge repository clone.
    # A failed/unavailable source is a HARD error: never fabricate benchmark documents.
    with tempfile.TemporaryDirectory(prefix='test98-fetch-',dir=str(path)) as stage:
        source=pathlib.Path(stage)
        records=[];total=0
        for name in FILES:
            url=('https://raw.githubusercontent.com/simdjson/simdjson-data/'
                 +SOURCE_COMMIT+'/jsonexamples/'+name)
            request=urllib.request.Request(url,headers={'User-Agent':'RVV-Test98-Immutable-Corpus/1.0'})
            with urllib.request.urlopen(request,timeout=120) as response:
                data=response.read(MAX_FILE+1)
            total+=len(data)
            if not data or len(data)>MAX_FILE or total>MAX_TOTAL:
                raise RuntimeError('Public fixture size exceeds 40MiB/file or 200MiB total: '+name)
            strict_json(data)  # complete document must be valid JSON
            (source/name).write_bytes(data)
            records.append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                            'source_path':'jsonexamples/'+name,'immutable_url':url})
            print('Fetched',name,len(data),'bytes',flush=True)
        manifest={'schema':1,'corpus_id':CORPUS_ID,'source_url':SOURCE_URL,
                  'upstream_commit':SOURCE_COMMIT,'files':records,
                  'selection':'18 published example fixtures used by JSON parser benchmarking; excludes random.json, repeat.json and NDJSON; includes real-world-derived and illustrative samples; no synthetic generation in Test98',
                  'license_notice':'Review upstream per-file provenance/license before redistributing corpus bytes; do not commit ZIP to repository'}
        tmp=path/(dest.name+'.partial')
        try:
            with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
                z.writestr('manifest.json',json_dump(manifest))
                for rec in records:
                    z.write(source/rec['name'],'files/'+rec['name'])
            verify(tmp)
            os.replace(tmp,dest)
        finally:tmp.unlink(missing_ok=True)
    print(json.dumps({'archive':str(dest),'sha256':sha(dest),'files':len(records),'cached':False}))

def extract(archive,destination):
    manifest=verify(archive)
    target=pathlib.Path(destination).resolve()
    # Content-addressed installation: reject a different existing corpus; never clobber a running test.
    root=target/CORPUS_ID
    if root.exists():
        lock=root/'manifest.json'
        if lock.exists() and json.loads(lock.read_text(encoding='utf8'))==manifest:
            for record in manifest['files']:
                f=root/'files'/record['name']
                if not f.is_file() or sha(f)!=record['sha256']:raise ValueError('Installed corpus tampered with: '+str(f))
            print(str(root));return
        raise ValueError('Corpus cache exists but does not match pinned manifest')
    target.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='test98-unpack-',dir=str(target)) as scratch:
        staging=pathlib.Path(scratch)/CORPUS_ID
        (staging/'files').mkdir(parents=True)
        with zipfile.ZipFile(archive) as z:
            (staging/'manifest.json').write_bytes(z.read('manifest.json'))
            for rec in manifest['files']:
                (staging/'files'/rec['name']).write_bytes(z.read('files/'+rec['name']))
        os.rename(staging,root)
    print(str(root))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    subs=p.add_subparsers(dest='action',required=True)
    a=subs.add_parser('prepare');a.add_argument('--cache',required=True)
    a=subs.add_parser('verify');a.add_argument('archive')
    a=subs.add_parser('extract');a.add_argument('archive');a.add_argument('destination')
    args=p.parse_args()
    if args.action=='prepare':prepare(args.cache)
    elif args.action=='verify':print(json.dumps({'sha256':sha(args.archive),'manifest':verify(args.archive)}))
    else:extract(args.archive,args.destination)
if __name__=='__main__':main()
