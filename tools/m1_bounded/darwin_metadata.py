"""Darwin fixed-buffer no-follow FD metadata, no path API fallback.

Unsupported OS/volume/API/owner/flags refuses. O_SYMLINK binds the link inode.
The raw getattrlist security blob preserves ACL order and absence; no text parse.
"""
import ctypes as C
import os
import struct
import sys
from ledger import Stop

MAX_ATTR=8192
MAX_NAMES=32768
MAX_XATTRS=128
MAX_VALUES=65536
# birth, modification, access, backup times and extended security.
MASK=0x200|0x400|0x1000|0x2000|0x400000
class Attr(C.Structure):
    _fields_=[('count',C.c_uint16),('reserved',C.c_uint16),('common',C.c_uint32),('vol',C.c_uint32),('dir',C.c_uint32),('file',C.c_uint32),('fork',C.c_uint32)]

class Metadata:
    def __init__(self):
        if sys.platform!='darwin' or os.geteuid()==0:
            raise Stop('unsupported')
        self.c=C.CDLL('/usr/lib/libc.dylib',use_errno=True)
        signatures={
            'fgetattrlist':([C.c_int,C.POINTER(Attr),C.c_void_p,C.c_size_t,C.c_ulong],C.c_int),
            'fsetattrlist':([C.c_int,C.POINTER(Attr),C.c_void_p,C.c_size_t,C.c_ulong],C.c_int),
            'flistxattr':([C.c_int,C.c_void_p,C.c_size_t,C.c_int],C.c_ssize_t),
            'fgetxattr':([C.c_int,C.c_char_p,C.c_void_p,C.c_size_t,C.c_uint32,C.c_int],C.c_ssize_t),
            'fsetxattr':([C.c_int,C.c_char_p,C.c_void_p,C.c_size_t,C.c_uint32,C.c_int],C.c_int),
            'fchflags':([C.c_int,C.c_uint32],C.c_int)}
        for name,(args,ret) in signatures.items():
            fn=getattr(self.c,name);fn.argtypes=args;fn.restype=ret

    def call(self,name,*args):
        result=getattr(self.c,name)(*args)
        if result<0: raise OSError(C.get_errno(),name)
        return result

    def attributes(self,fd):
        buf=C.create_string_buffer(MAX_ATTR);attrs=Attr(5,0,MASK,0,0,0,0)
        self.call('fgetattrlist',fd,C.byref(attrs),buf,MAX_ATTR,0)
        size=struct.unpack_from('=I',buf.raw)[0]
        # four 16-byte timespecs + attrreference, then bounded security blob.
        if not 76<=size<=MAX_ATTR:raise Stop('metadata')
        raw=buf.raw[:size];offset,length=struct.unpack_from('=iI',raw,68)
        if length>MAX_ATTR-76 or 68+offset<76 or 68+offset+length>size:raise Stop('metadata')
        return raw[4:]

    def xattrs(self,fd):
        names=C.create_string_buffer(MAX_NAMES)
        n=self.call('flistxattr',fd,names,MAX_NAMES,0x20) # SHOWCOMPRESSION, no omission
        if n>MAX_NAMES:raise Stop('metadata')
        raw=names.raw[:n]
        if raw and raw[-1]!=0:raise Stop('metadata')
        keys=raw[:-1].split(b'\0') if raw else []
        if len(keys)>MAX_XATTRS or len(set(keys))!=len(keys) or any(not 1<=len(x)<=255 for x in keys):raise Stop('metadata')
        result=[];total=0
        for key in sorted(keys):
            value=C.create_string_buffer(MAX_VALUES)
            size=self.call('fgetxattr',fd,key,value,MAX_VALUES,0,0x20)
            total+=size
            if total>MAX_VALUES:raise Stop('metadata')
            result.append((key.hex(),value.raw[:size].hex()))
        return result

    def capture(self,fd):
        st=os.fstat(fd)
        if st.st_uid!=os.geteuid() or st.st_gid not in set(os.getgroups()+[os.getegid()]):raise Stop('unsupported')
        # UF_NODUMP is supported. Immutable/append/compression/unknown flags STOP.
        if st.st_flags & ~1:raise Stop('unsupported')
        return {'uid':st.st_uid,'gid':st.st_gid,'mode':st.st_mode&0o7777,'flags':st.st_flags,
                'attributes':self.attributes(fd).hex(),'xattrs':self.xattrs(fd)}

    @staticmethod
    def effect_bytes(meta):
        # Exact logical API input bytes, including repeated timestamp restoration:
        # fchown gid(4), chmod(4), xattr name incl NUL+value, attrs blob twice,
        # flags(4). Not physical allocation or syscall/native closure.
        attrs=bytes.fromhex(meta['attributes'])
        security_length=struct.unpack_from('=iI',attrs,64)[1]
        return 12+128+(8+security_length if security_length else 0)+sum(len(bytes.fromhex(k))+1+len(bytes.fromhex(v)) for k,v in meta['xattrs'])

    def restore(self,fd,meta,content_check):
        if meta['uid']!=os.geteuid() or meta['gid'] not in set(os.getgroups()+[os.getegid()]) or meta['flags']&~1:raise Stop('unsupported')
        if self.xattrs(fd):raise Stop('metadata') # inherited attrs not silently deleted
        if os.fstat(fd).st_gid!=meta['gid']:os.fchown(fd,-1,meta['gid'])
        os.fchmod(fd,meta['mode'])
        for key,value in meta['xattrs']:
            k=bytes.fromhex(key);v=bytes.fromhex(value)
            self.call('fsetxattr',fd,k,C.c_char_p(v),len(v),0,2) # CREATE, never replace
        attrs=bytes.fromhex(meta['attributes'])
        offset,length=struct.unpack_from('=iI',attrs,64)
        security=attrs[64+offset:64+offset+length]
        if length:
            value=struct.pack('=iI',8,length)+security
            a=Attr(5,0,0x400000,0,0,0,0)
            self.call('fsetattrlist',fd,C.byref(a),C.c_char_p(value),len(value),0)
        else:
            current=self.attributes(fd)
            if struct.unpack_from('=iI',current,64)[1]!=0:raise Stop('metadata')
        # Darwin rejects an empty security attrreference as a setter. Preserve
        # genuine absence by requiring absent destination security, no deletion.
        a=Attr(5,0,MASK & ~0x400000,0,0,0,0)
        self.call('fsetattrlist',fd,C.byref(a),C.c_char_p(attrs[:64]),64,0)
        self.call('fchflags',fd,meta['flags'])
        content_check() # regular hash reads can advance atime
        self.call('fsetattrlist',fd,C.byref(a),C.c_char_p(attrs[:64]),64,0)
        actual=self.capture(fd)
        if actual!=meta:raise Stop('metadata')
        return actual
