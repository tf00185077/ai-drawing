"""D3 previous schema copied from exact pre-task ORM; whole-schema/value audit."""
import json
from pathlib import Path
import sqlite3
import socket
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.db import database
from app.db.models import DownloadedResource

FIXTURE=Path(__file__).parent/'fixtures/resources/previous-schema.sql'


def audit(engine):
    with engine.connect() as c:
        names=[r[0] for r in c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {name:{'schema':[list(r) for r in c.exec_driver_sql("SELECT name,type,sql FROM sqlite_master WHERE tbl_name=? ORDER BY name",(name,))], 'columns':[(col['name'],str(col['type']),col['nullable'],col['default']) for col in inspect(engine).get_columns(name)],
                      'values':[list(r) for r in c.exec_driver_sql('SELECT * FROM "'+name+'" ORDER BY 1').fetchall()]}
                for name in names}


def test_startup_backfill_whole_old_schema_values_aliases_and_files_preserved(tmp_path,monkeypatch):
    from app.services.resource_record_backfill import backfill_metadata
    from app.services.resource_records import project_resource
    old=tmp_path/'previous.db'; con=sqlite3.connect(old);con.executescript(FIXTURE.read_text())
    model=tmp_path/'synthetic.safetensors';model.write_bytes(b'do not touch')
    notes=[json.dumps({'base_model':'Pony','model_family':'sdxl','trainedWords':[' a ','a'],'expected_size_bytes':123}),
           'not json TOKEN_SENTINEL','[]',json.dumps({'base_model':'SD 1.5'}),
           json.dumps({'base_model':'Illustrious','civitai_file_id':999,'sha256':'b'*64}),
           json.dumps({'base_model':'NoobAI'}),None,
           json.dumps({'base_model':'Pony','model_family':'Anima 99'})]
    for id,note in enumerate(notes,1):
        con.execute('INSERT INTO downloaded_resources (id,resource_name,resource_type,provider,source_url,local_path,sha256,model_id,version_id,civitai_file_id,status,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (id,'kept-'+str(id),'lora','civitai','https://civitai.com/models/10?token=TOKEN_SENTINEL',str(model) if id==1 else str(tmp_path/'offline'), 'a'*64,'10','21','32' if id in {1,6} else str(100+id),'installed',note))
    # Synthetic sentinels in independent legacy tables, including every alias/history column.
    for table in ['civitai_source_alias_registry_records','civitai_source_aliases','civitai_source_alias_history','civitai_source_alias_repoint_transitions','civitai_source_alias_backfill_candidates']:
        exists=con.execute('SELECT name FROM sqlite_master WHERE type="table" AND name=?',(table,)).fetchone()
        if not exists: continue
        cols=con.execute('PRAGMA table_info("'+table+'")').fetchall()
        values={c[1]:(1 if 'INT' in c[2] else 'synthetic-'+c[1]) for c in cols}
        values.update({k:'a'*64 for k in values if k.endswith('sha256')})
        if 'operation' in values: values['operation']='rename'
        if 'alias_kind' in values: values['alias_kind']='primary'
        names=','.join('"'+k+'"' for k in values)
        con.execute('INSERT INTO "'+table+'" ('+names+') VALUES ('+','.join('?' for _ in values)+')',list(values.values()))
    con.commit();con.close()
    engine=create_engine('sqlite:///'+str(old)); before=audit(engine); bodies={model:model.read_bytes()}
    monkeypatch.setattr(database,'engine',engine)
    def denied(*a,**kw): raise AssertionError('network/model-body access forbidden during startup/backfill')
    monkeypatch.setattr(socket,'create_connection',denied)
    # Filesystem stat availability is allowed; no model-body reads or writes.
    original=Path.open
    def guarded(self,*a,**kw):
        if self==model: return denied()
        return original(self,*a,**kw)
    monkeypatch.setattr(Path,'open',guarded)
    database.init_db(); after_start=audit(engine)
    assert set(after_start)-set(before)=={'download_jobs','download_claims','download_components'}
    assert all(not after_start[t]['values'] for t in set(after_start)-set(before))
    assert set(before)<=set(after_start)
    for table,old_value in before.items():
        now=after_start[table]
        assert now['columns'][:len(old_value['columns'])]==old_value['columns']
        assert [r[:len(old_value['columns'])] for r in now['values']]==old_value['values']
        if table!='downloaded_resources': assert now==old_value
    assert [c[0] for c in after_start['downloaded_resources']['columns'][len(before['downloaded_resources']['columns']):]]==['metadata_json']
    Session=sessionmaker(bind=engine)
    with Session() as db:
        assert all(r.metadata_json is None for r in db.query(DownloadedResource))
        report=backfill_metadata(db)
        projections=[project_resource(r).model_dump() for r in db.query(DownloadedResource).order_by(DownloadedResource.id)]
        rows=db.query(DownloadedResource).order_by(DownloadedResource.id).all()
        assert [r.notes for r in rows]==notes
        codes={id:{d['code'] for d in ds} for id,ds in report.items()}
        assert 'duplicate_legacy_candidate' in codes[1] and 'duplicate_legacy_candidate' in codes[6]
        assert 'malformed_legacy_notes' in codes[2] and 'malformed_legacy_notes' in codes[3]
        assert 'no_matching_workflow' in codes[4]
        assert 'conflicting_legacy_identity' in codes[5]
        assert 'path_unavailable' in codes[2] and 'conflicting_legacy_metadata' in codes[8]
        assert all(p['sha256_verified'] is None for p in projections)
        first=audit(engine)
        assert backfill_metadata(db)==report
        assert [project_resource(r).model_dump() for r in rows]==projections
    database.init_db(); assert audit(engine)==first
    for table,value in before.items():
        assert [r[:len(value['columns'])] for r in first[table]['values']]==value['values']
    monkeypatch.setattr(Path,'open',original)
    assert {p:p.read_bytes() for p in bodies}==bodies
    # Retain replayable synthetic aggregate/schema proof only when requested.
    import os
    if os.environ.get('RESOURCE_SCHEMA_AUDIT'):
        Path(os.environ['RESOURCE_SCHEMA_AUDIT']).write_text(json.dumps({'before':before,'after_startup':after_start,'after_backfill':first,'diagnostics':report},indent=2,default=str)+'\n')
