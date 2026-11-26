"""Independent official-byte reconstruction; never seed candidate from local Git."""
import gzip,hashlib,io,json,os,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]; OUT=Path(__file__).resolve().parent
S=Path(os.environ['PAPERCLIP_RUN_SCRATCH_DIR']); IDX=json.loads((S/'p203-correction2-delivery-index.json').read_text())
F=IDX['final']; B=IDX['base']; T=IDX['tree']; operations=[]
env={k:os.environ[k] for k in ['PATH','LANG'] if k in os.environ}
env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_TERMINAL_PROMPT='0')
def run(args,data=None,ok=True):
 r=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=S)
 operations.append(dict(argv=list(map(str,args)),exit_code=r.returncode,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace')))
 if ok: assert r.returncode==0,operations[-1]
 return r
parts=IDX['prerequisite']['parts']; pack=b''.join((S/p['filename']).read_bytes() for p in parts)
assert len(pack)==IDX['prerequisite']['bytes'] and hashlib.sha256(pack).hexdigest()==IDX['prerequisite']['sha256']
(S/'qa3-prerequisite.pack').write_bytes(pack)
stores=[]
for name in ['qa3-bundle.git','qa3-patch.git']:
 d=S/name; run(['git','init','--bare',str(d)]); g=['git','--git-dir',str(d)]
 run(g+['index-pack','--stdin'],pack)
 (d/'shallow').write_text('\n'.join(IDX['prerequisite']['shallow'])+'\n')
 run(g+['update-ref','refs/heads/base',B])
 assert run(g+['cat-file','-e',F],ok=False).returncode!=0
 assert not (d/'objects/info/alternates').exists()
 stores.append(g)
g=stores[0]; run(g+['bundle','verify',str(S/'p203-correction2.bundle')]); run(g+['fetch',str(S/'p203-correction2.bundle'),'HEAD:refs/heads/candidate'])
assert run(g+['rev-parse','candidate']).stdout.decode().strip()==F
assert run(g+['rev-parse','candidate^{tree}']).stdout.decode().strip()==T
bundle_fsck=run(g+['fsck','--full']).returncode
patch=gzip.decompress((S/'p203-correction2-full-index.patch.gz').read_bytes()); (S/'qa3-candidate.patch').write_bytes(patch)
g=stores[1];run(g+['read-tree',B]);run(g+['apply','--cached','--binary',str(S/'qa3-candidate.patch')])
assert run(g+['write-tree']).stdout.decode().strip()==T
patch_fsck=run(g+['fsck','--full']).returncode
# Read restored bundle blobs in batch and independently verify every ordinary body/mode.
g=stores[0]; listing=run(g+['ls-tree','-r','-z',F]).stdout
rows={}
for record in listing.split(b'\0'):
 if not record:continue
 head,path=record.split(b'\t');mode,kind,oid=head.decode().split()
 if kind=='blob': rows[path.decode()]=(mode,oid)
expected=json.loads((S/'p203-correction2-fingerprints.json').read_text())['files']
assert set(rows)==set(expected)
ids=sorted({v[1] for v in rows.values()}); raw=subprocess.check_output(g+['cat-file','--batch'],input=('\n'.join(ids)+'\n').encode(),env=env)
buf=io.BytesIO(raw); blobs={}
for oid in ids:
 header=buf.readline().decode().split(); assert header[0]==oid and header[1]=='blob'
 body=buf.read(int(header[2]));assert buf.read(1)==b'\n';blobs[oid]=body
for path,(mode,oid) in rows.items():
 body=blobs[oid];assert expected[path]==dict(mode=mode,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()),path
with tarfile.open(S/'p203-correction2-delivery.tar.gz') as archive:
 members=archive.getmembers();manifest=json.load(archive.extractfile('DELIVERY-MANIFEST.json'));count=0
 for member in members:
  assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
  if member.name=='DELIVERY-MANIFEST.json':continue
  body=archive.extractfile(member).read();mode,oid=rows[member.name]
  assert body==blobs[oid] and bool(member.mode&0o111)==(mode=='100755'),member.name
  assert manifest['payloads'][member.name]==expected[member.name];count+=1
 assert count==111 and len(members)==112
assert (S/'p203-correction2-manifest.md').read_bytes()==blobs[rows['docs/tasks/p2-03-bounded-download/manifest.md'][1]]
result=dict(final=F,tree=T,base=B,official_attachments_checked=17,prerequisite_bytes=len(pack),prerequisite_sha256=hashlib.sha256(pack).hexdigest(),candidate_absent_before_import=True,no_alternates=True,bundle_exact=True,patch_exact=True,bundle_fsck=bundle_fsck,patch_fsck=patch_fsck,ordinary_fingerprints_modes_exact=len(rows),archive_members=len(members),archive_git_payloads=count,manifest_exact=True,operations=operations)
(OUT/'independent-coding-restore.json').write_text(json.dumps(result,indent=2)+'\n')
print('Exact official restore:',F,T,len(rows),'files',len(members),'members',count,'payloads; both fsck0')
