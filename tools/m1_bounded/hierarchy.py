"""Explicit synthetic named trees. No product imports, discovery or live binding."""
import hashlib
import os
from pathlib import Path
import re
import stat
import time
from types import MappingProxyType
from ledger import Stop, Window, CHUNK, bounded_json, directory, inode, path_parts, close_once
from darwin_metadata import Metadata

MAX_ENTRIES=100000
META_BYTES=196608
MANIFEST_BYTES=16777216

def pin(st):
    return (st.st_dev,st.st_ino,st.st_mode,st.st_nlink,st.st_uid,st.st_gid,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_flags)

def companion_name(ledger,name):
    path_parts(ledger)
    if '/' in ledger:raise Stop('path')
    if name in (ledger,ledger+'.owner',ledger+'.checkpoint'):return True
    return bool(re.fullmatch(r'\.'+re.escape(ledger)+r'(?:\.checkpoint)?\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.tmp',name))

class Manifest:
    """roots={label:absolute synthetic root}; entries=[(label,relative,type)].

    Every directory's immediate children must exactly equal listed entries.
    Links require covered target inode/path; directory targets require full tree.
    Nothing follows a link while reading. No absent source or unknown hardlink.
    """
    def __init__(self,roots,entries,seconds=35):
        if type(roots)is not dict or not 1<=len(roots)<=16 or type(entries)not in(list,tuple) or not 1<=len(entries)<=MAX_ENTRIES or not 0<seconds<=35:
            raise Stop('plan')
        self.meta=Metadata();self.roots={};self.records={};self.fds={};self.deadline=time.monotonic()+seconds
        paths=[];seen=set()
        try:
            for label,path in roots.items():
                if len(path_parts(label))!=1:raise Stop('path')
                p=Path(path)
                if any(p==q or p in q.parents or q in p.parents for q in paths):raise Stop('alias')
                fd=directory(p);st=os.fstat(fd)
                if inode(st) in seen:os.close(fd);raise Stop('alias')
                seen.add(inode(st));paths.append(p);self.roots[label]=(p,fd,inode(st))
            declared={}
            represented=2
            for label,path,kind in entries:
                path_parts(path)
                if label not in self.roots or kind not in ('file','dir','link') or (label,path)in declared:raise Stop('collision')
                declared[label,path]=kind
            # Roots are custody/identity anchors, not implicitly copied entries.
            for label,path in declared:
                parts=path.split('/')
                for i in range(1,len(parts)):
                    if declared.get((label,'/'.join(parts[:i])))!='dir':raise Stop('plan')
            for (label,path),kind in sorted(declared.items(),key=lambda kv:(kv[0][1].count('/'),kv[0])):
                self.tick();parent,name=self.parent(label,path)
                before=os.stat(name,dir_fd=parent,follow_symlinks=False)
                mode=stat.S_IFMT(before.st_mode)
                if mode!={'file':stat.S_IFREG,'dir':stat.S_IFDIR,'link':stat.S_IFLNK}[kind] or (kind!='dir' and before.st_nlink!=1):raise Stop('type')
                if inode(before) in seen:raise Stop('alias')
                seen.add(inode(before))
                flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
                if kind=='dir':flags|=os.O_DIRECTORY
                if kind=='link':flags=(os.O_RDONLY|0x00200000|os.O_NONBLOCK) # Darwin O_SYMLINK
                fd=os.open(name,flags,dir_fd=parent);self.fds[label,path]=fd
                if pin(os.fstat(fd))!=pin(before):raise Stop('drift')
                literal=os.readlink(name,dir_fd=parent) if kind=='link' else None
                if literal is not None and len(os.fsencode(literal))>1024:raise Stop('limit')
                meta=self.meta.capture(fd)
                digest=self.hash_fd(fd,before.st_size) if kind=='file' else None
                if pin(os.fstat(fd))!=pin(before) or pin(os.stat(name,dir_fd=parent,follow_symlinks=False))!=pin(before):raise Stop('drift')
                record={'root':label,'path':path,'kind':kind,'identity':list(pin(before)),
                        'size':before.st_size if kind=='file' else len(os.fsencode(literal)) if kind=='link' else 0,
                        'sha256':digest,'literal':literal,'metadata':meta}
                represented+=len(bounded_json(record,META_BYTES))+1
                if represented>MANIFEST_BYTES:raise Stop('limit')
                self.records[label,path]=record
            self.check_sets(declared)
            for key,r in self.records.items():
                if r['kind']=='link':
                    p=self.roots[key[0]][0]/key[1]
                    target=Path(os.path.normpath(os.path.join(str(p.parent),r['literal'])))
                    matches=[k for k in self.records if self.roots[k[0]][0]/k[1]==target]
                    if len(matches)!=1 or self.records[matches[0]]['kind']=='link':raise Stop('plan')
                    r['target']=list(matches[0]) # covered once; no follow/extra root
            # Freeze a detached, bounded canonical byte representation.
            self.encoded=bounded_json(list(self.records.values()),MANIFEST_BYTES)
            self.digest=hashlib.sha256(self.encoded).hexdigest()
        except BaseException:
            active=__import__('sys').exc_info()[1]
            try:self.close()
            except Exception:pass
            raise active

    def tick(self):
        if time.monotonic()>self.deadline:raise Stop('deadline')

    def parent(self,label,path):
        parts=path.split('/')
        return (self.roots[label][1] if len(parts)==1 else self.fds[label,'/'.join(parts[:-1])]),parts[-1]

    def check_sets(self,declared):
        for label in self.roots:
            dirs=['']+[p for (l,p),k in declared.items() if l==label and k=='dir']
            for p in dirs:
                self.tick();fd=self.roots[label][1] if not p else self.fds[label,p]
                expected={q.split('/')[-1] for (l,q)in declared if l==label and q.rpartition('/')[0]==p}
                actual=set()
                with os.scandir(fd) as it:
                    for entry in it:
                        self.tick()
                        if len(actual)>=MAX_ENTRIES or len(os.fsencode(entry.name))>64:raise Stop('limit')
                        actual.add(entry.name)
                if actual!=expected:raise Stop('drift')

    def hash_fd(self,fd,size):
        os.lseek(fd,0,0);h=hashlib.sha256();remaining=size
        while remaining:
            self.tick();raw=os.read(fd,min(CHUNK,remaining))
            if not raw:raise Stop('drift')
            h.update(raw);remaining-=len(raw)
        if os.read(fd,1):raise Stop('drift')
        return h.hexdigest()

    def verify(self):
        for label,(p,fd,identity) in self.roots.items():
            current=directory(p)
            try:
                if inode(os.fstat(current))!=identity:raise Stop('drift')
            finally:close_once(current)
        for (label,path),r in self.records.items():
            parent,name=self.parent(label,path)
            if list(pin(os.stat(name,dir_fd=parent,follow_symlinks=False)))!=r['identity'] or list(pin(os.fstat(self.fds[label,path])))!=r['identity']:raise Stop('drift')
        self.check_sets({k:r['kind'] for k,r in self.records.items()})
        if hashlib.sha256(bounded_json(list(self.records.values()),len(self.encoded))).hexdigest()!=self.digest:raise Stop('drift')

    def close(self):
        errors=[]
        for key in list(self.fds):
            fd=self.fds.pop(key)
            try:os.close(fd)
            except BaseException as e:errors.append(e)
        for key in list(self.roots):
            _,fd,_=self.roots.pop(key)
            try:os.close(fd)
            except BaseException as e:errors.append(e)
        if errors:raise errors[0]

    def plan(self):
        slots={'controls/error':('file',256),'controls/manifest':('file',len(self.encoded))}
        # One full storage copy plus one independent restore payload. Literal
        # bytes are full storage representation + symlink native literal bytes.
        for i,((label,path),r) in enumerate(self.records.items()):
            storage='pre-adoption/'+label+'/'+path
            restore='restore-check/'+label+'/'+path
            for stage in ('pre-adoption','restore-check'):
                slots[stage+'/'+label]=('dir',0)
            if r['kind']=='dir':slots[storage]=('dir',0);slots[restore]=('dir',0)
            else:slots[storage]=('file',r['size']);slots[restore]=('native' if r['kind']=='link' else 'file',r['size'])
            rmeta=bounded_json(r,META_BYTES)
            slots['controls/meta-'+label+'-'+str(i)]=('file',len(rmeta))
            slots['controls/meta2-'+label+'-'+str(i)]=('file',len(rmeta))
            slots['controls/readback-'+label+'-'+str(i)]=('file',len(bounded_json(r['metadata'],META_BYTES)))
            slots['controls/native-'+label+'-'+str(i)]=('native',self.meta.effect_bytes(r['metadata']))
        return slots

    def protect(self,w):
        def action():
            self.verify()
            expected=self.plan()
            if any(w.plan.get(p)!=v for p,v in expected.items()):raise Stop('plan')
            w.stream('controls/manifest',[self.encoded[i:i+CHUNK] for i in range(0,len(self.encoded),CHUNK)])
            # Containers then declared dirs before children.
            for p,spec in sorted(expected.items(),key=lambda kv:(kv[0].count('/'),kv[0])):
                if spec[0]=='dir':w.mkdir(p)
            for i,((label,path),r) in enumerate(self.records.items()):
                self.verify();src=self.fds[label,path];storage='pre-adoption/'+label+'/'+path;restore='restore-check/'+label+'/'+path
                meta_slot='controls/meta-'+label+'-'+str(i)
                raw=bounded_json(r,META_BYTES)
                for meta_slot in (meta_slot,'controls/meta2-'+label+'-'+str(i)):
                    w.stream(meta_slot,[raw[x:x+CHUNK] for x in range(0,len(raw),CHUNK)])
                if r['kind']=='file':
                    def chunks():
                        os.lseek(src,0,0);remaining=r['size']
                        while remaining:
                            self.verify();raw=os.read(src,min(CHUNK,remaining))
                            if not raw:raise Stop('drift')
                            remaining-=len(raw);yield raw
                        self.verify()
                    w.stream(storage,chunks(),r['sha256'])
                    # Independently read the pinned original again; no hardlink/clone.
                    w.stream(restore,chunks(),r['sha256'])
                elif r['kind']=='link':
                    w.stream(storage,[os.fsencode(r['literal'])])
                    parent,name=w.parent_for(restore)
                    w.effect(restore,r['size'],lambda:os.symlink(r['literal'],name,dir_fd=parent))
            w.phase='restore'
            # Bottom-up metadata so parent restrictions cannot affect child creation.
            for i,((label,path),r) in sorted(enumerate(self.records.items()),key=lambda kv:-kv[1][0][1].count('/')):
                restore='restore-check/'+label+'/'+path;parent,name=w.parent_for(restore)
                flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
                if r['kind']=='dir':flags|=os.O_DIRECTORY
                if r['kind']=='link':flags=os.O_RDONLY|0x00200000|os.O_NONBLOCK
                fd=os.open(name,flags,dir_fd=parent)
                try:
                    def readback():
                        if r['kind']=='file' and self.hash_fd(fd,r['size'])!=r['sha256']:raise Stop('hash')
                        if r['kind']=='link' and os.readlink(name,dir_fd=parent)!=r['literal']:raise Stop('drift')
                    slot='controls/native-'+label+'-'+str(i)
                    actual=w.effect(slot,self.meta.effect_bytes(r['metadata']),lambda:self.meta.restore(fd,r['metadata'],readback))
                    encoded=bounded_json(actual,META_BYTES)
                    w.stream('controls/readback-'+label+'-'+str(i),[encoded[x:x+CHUNK] for x in range(0,len(encoded),CHUNK)])
                finally:close_once(fd)
                if r['kind']=='dir':w.sealed.add(restore)
            self.verify()
            return dict(status='fixture_roundtrip',manifest_sha256=self.digest,entries=len(self.records),
                        protection_verified=False,source_start_allowed=False,retry_b_allowed=False,commit_state=w.commit)
        return w.run('copy',action)
