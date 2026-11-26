"""Additional registered-boundary checks, using the candidate's lower HTTP/storage fixture."""
import importlib.util,pathlib,struct,zlib,io
from PIL import Image
import pytest
p=pathlib.Path(__file__).resolve().parents[4]/'mcp-server/tests/test_gallery_content.py'
spec=importlib.util.spec_from_file_location('qa_lower_content_fixtures',p);lower=importlib.util.module_from_spec(spec);spec.loader.exec_module(lower)
content_backend=lower.content_backend

def broken_pixels():
 # Valid PNG structure and CRC, invalid deflate stream. verify() alone accepts.
 out=io.BytesIO();Image.new('RGB',(8,9),'red').save(out,format='PNG');raw=out.getvalue();chunks=[];i=8
 while i<len(raw):
  n=struct.unpack('>I',raw[i:i+4])[0];kind=raw[i+4:i+8];body=raw[i+8:i+8+n]
  if kind==b'IDAT':body=b'not a zlib stream'
  chunk=kind+body;chunks.append(struct.pack('>I',len(body))+chunk+struct.pack('>I',zlib.crc32(chunk)));i+=12+n
 return raw[:8]+b''.join(chunks)

async def test_crc_valid_but_undecodable_pixels(content_backend):
 raw=broken_pixels()
 with Image.open(io.BytesIO(raw),formats=['PNG']) as image:image.verify()
 _,path,_,_,_,_=content_backend;path.write_bytes(raw)
 lower.error(await lower.read(artifact_id=73,include_content=True),'artifact_content_invalid')

@pytest.mark.parametrize('args',[{'artifact_id':False},{'artifact_id':73.0},{'image_id':True},{'artifact_id':73,'include_content':1},{'artifact_id':73,'include_content':None}])
async def test_extra_coercions_rejected_without_backend(content_backend,args):
 *_,requests,response=content_backend
 lower.error(await lower.read(**{'include_content':True,**args}),'request_validation_failed');assert requests==[]
