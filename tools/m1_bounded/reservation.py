"""One-shot cooperative finite-child lease over one immutable operation ledger.

No new root, counter, cap, refund, reset, production entry or native confinement.
Python callers must use this API cooperatively; arbitrary in-process mutation is
not a security boundary. A digest binds the full parent plan, not just four slots.
"""
from contextlib import contextmanager
from types import MappingProxyType
import threading
from ledger import Window,OperationBinding,Stop,CAP

CAPTURE=('controls/stdout','controls/stderr','controls/error','controls/receipt')
_KEY=object()

def reserve(parent,binding):
    if type(parent) is not Window or type(binding) is not OperationBinding:
        raise Stop('plan')
    if not parent.lock.acquire(False):raise Stop('busy')
    try:
        if parent._running or parent._child_active is not None or parent._mutation_depth:raise Stop('busy')
        if parent.stopped or parent.commit=='unknown' or parent._close_state!='open':raise Stop('stopped')
        if parent.binding is None or binding!=parent.binding:raise Stop('plan')
        if any(p not in parent.plan or parent.plan[p][0]!='file' or p in parent.used or p in parent._leases for p in CAPTURE):raise Stop('plan')
        if parent.plan['controls/error']!=('file',256) or parent.plan['controls/receipt']!=('file',32768):raise Stop('plan')
        if sum(v[1] for v in parent.plan.values())>CAP:raise Stop('limit')
        # Existing root/controls are borrowed; no effect or new descriptor here.
        view=ChildReservation(_KEY,parent)
        for p in CAPTURE:parent._leases[p]=view
        return view
    finally:parent.lock.release()

class ChildReservation:
    def __init__(self,key,parent):
        if key is not _KEY:raise Stop('plan')
        self._parent=parent;self._origin=parent;self._binding=parent.binding
        self._root_id=parent.root_id;self._parent_id=parent.parent_id
        self._digest=parent._plan_digest
        self._plan=MappingProxyType({p:parent.plan[p] for p in CAPTURE})
        self._state='issued';self._owner=None

    @property
    def plan(self):return self._plan
    @property
    def used(self):return self._parent.used.intersection(self.plan)
    @property
    def charged(self):return MappingProxyType({p:self._parent.charged[p] for p in self.plan if p in self._parent.charged})
    @property
    def stopped(self):return self._parent.stopped
    @stopped.setter
    def stopped(self,value):self._parent.stopped=value
    @property
    def _running(self):return self._parent._running
    @_running.setter
    def _running(self,value):self._parent._running=value
    @property
    def _finite_child_active_fds(self):return getattr(self._parent,'_finite_child_active_fds',{})
    @_finite_child_active_fds.setter
    def _finite_child_active_fds(self,value):self._parent._finite_child_active_fds=value
    def __getattr__(self,name):
        if name in ('parent','name','root','parent_fd','root_fd','parent_id','root_id','fds','ids','sealed','lock','commit'):
            return getattr(self._parent,name)
        raise AttributeError(name)

    def validate_binding(self):
        p=self._parent
        if p is not self._origin or p.binding is not self._binding or p._plan_digest!=self._digest or p.root_id!=self._root_id or p.parent_id!=self._parent_id:
            raise Stop('drift')
        if any(p._leases.get(n) is not self or p.plan.get(n)!=self.plan[n] for n in CAPTURE):raise Stop('plan')

    def binding_receipt(self):
        self.validate_binding();b=self._binding
        return {'operation_id':b.operation_id,'epoch':b.epoch,'source_id':b.source_id,'parent_plan_sha256':self._digest,'parent_root_identity':[str(n) for n in self._root_id]}

    def validate_spec(self,spec):
        self.validate_binding()
        if spec.operation_id!=self._binding.operation_id:raise Stop('plan')
        if spec.source_id!=self._binding.source_id:raise Stop('source')

    def begin(self):
        # Controller holds the shared nonblocking lock through all finalization.
        self.validate_binding();p=self._parent
        if p._child_active is not None or p._running or p._mutation_depth:raise Stop('busy')
        if self._state!='issued' or self.used:raise Stop('spent')
        if p.stopped or p.commit=='unknown' or p._close_state!='open':raise Stop('stopped')
        self._state='entered';self._owner=threading.get_ident();p._child_active=self

    def check_active(self):
        self.validate_binding();p=self._parent
        if self._state!='entered' or self._owner!=threading.get_ident() or p._child_active is not self:raise Stop('spent')
        if p.stopped or p.commit=='unknown' or p._close_state!='open':raise Stop('stopped')

    def finish(self,complete):
        p=self._parent
        # Reservation is consumed on every entered attempt, including pre-effect
        # refusal, cancellation and uncertainty. Nothing returns capacity.
        if not complete:p.stopped=True
        self._state='spent';self._owner=None;p._child_active=None

    @contextmanager
    def _mutation(self,path):
        self.validate_binding()
        if path not in self.plan:raise Stop('plan')
        if self._state!='entered' or self._owner!=threading.get_ident() or self._parent._child_active is not self:raise Stop('spent')
        with self._parent._mutation(path,self):yield

    def _charge(self,path,kind):
        with self._mutation(path):self._parent._charge(path,kind,self)

    def snapshot(self):
        # Projection only; these exact charges already belong to the parent.
        total=sum(v[1] for v in self.plan.values());charged=sum(self.charged.values())
        return dict(plan_total=total,charged=charged,reserved_remaining=total-charged,
                    slots={p:{'charged':self.charged.get(p,0),'reserved':v[1]-self.charged.get(p,0)} for p,v in self.plan.items()},
                    stopped=self.stopped,commit_state=self.commit,protection_verified=False,source_start_allowed=False,retry_b_allowed=False)
