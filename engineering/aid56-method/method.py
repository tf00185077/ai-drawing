"""Offline arithmetic and evidence interpretation only; no collectors or I/O."""


def discovery(exit_code, stdout, *, timed_out=False, stderr_present=None):
    """Interpret retained pgrep-style results; never execute or retain stderr text.

    The adapter's exit semantics must be independently bound to its exact tool.
    no_match covers one query at one epoch, never global process absence.
    """
    if type(stdout) is not str or type(timed_out) is not bool:
        raise ValueError('invalid observation shape')
    if exit_code is not None and type(exit_code) is not int:
        raise ValueError('invalid exit code')
    if stderr_present is not None and type(stderr_present) is not bool:
        raise ValueError('invalid stderr projection')
    result = dict(state='error', pids=None, exit=exit_code,
                  stderr_present=stderr_present, cause='unknown')
    if timed_out:
        result['state'] = 'timeout'
    elif exit_code == 1:
        result['state'] = 'no_match' if not stdout.strip() else 'invalid_output'
    elif exit_code == 0:
        words = stdout.split()
        if words and all(w.isascii() and w.isdecimal() and int(w) > 0 for w in words):
            pids = [int(w) for w in words]
            if len(set(pids)) == len(pids):
                result.update(state='matched', pids=pids)
            else:
                result['state'] = 'invalid_output'
        else:
            result['state'] = 'invalid_output'
    return result


def _number(value):
    if type(value) is not int or value < 0:
        raise ValueError('nonnegative integer bytes required')
    return value


def protection(entries, *, complete):
    """Sum unique destination payloads, preserving link literals separately.

    id is a reviewer-resolved destination identity, not an inode: separate names
    get full-copy cost. Roots may overlap only at the same id. Targets must be
    explicitly included once; this function never follows a link.
    """
    if type(complete) is not bool:
        raise ValueError('explicit completeness required')
    unique = {}
    for entry in entries:
        ident = entry['id']
        if type(ident) is not str or not ident or entry['kind'] not in {'file', 'link'}:
            raise ValueError('invalid protection identity/kind')
        _number(entry['bytes'])
        if ident in unique and unique[ident] != entry:
            raise ValueError('conflicting destination identity')
        unique[ident] = entry
    missing = [] if complete else ['effective_roots']
    for entry in unique.values():
        if entry['kind'] == 'link':
            target = entry.get('target')
            if type(target) is not str or not target:
                raise ValueError('link requires resolved target identity')
            if target not in unique:
                missing.append('link_target:' + target)
            elif unique[target]['kind'] != 'file':
                missing.append('unresolved_link_target:' + target)
    return dict(bytes=None if missing else sum(e['bytes'] for e in unique.values()),
                missing=sorted(set(missing)), basis='complete_manifest' if not missing else 'unavailable')


def _bound(record):
    if record is None:
        return None
    value = record.get('bytes')
    if value is not None:
        _number(value)
    if (record.get('basis') not in {'complete_manifest', 'enforced_limit', 'derived'}
            or type(record.get('evidence')) is not str or not record['evidence'].strip()):
        return None
    return value


def sqlite_post_bound(page_size, current_pages, page_limit, companions):
    """Full later main-file ceiling plus *complete* later companion ceiling.

    page_limit.pages is a page count; all other Bound values are bytes.
    Requires a valid main-file length of current_pages*page_size (no unexplained
    trailing bytes), a verified actual cap on every relevant writer, fixed
    page size/no VACUUM or ATTACH escape, plus separately justified companions.
    This does not bound transient journals/temp/metadata or promise SQL success.
    """
    _number(page_size)
    _number(current_pages)
    if page_size < 512 or page_size > 65536 or page_size & (page_size - 1):
        raise ValueError('invalid SQLite page size')
    limit = None if page_limit is None else page_limit.get('pages')
    if limit is not None:
        _number(limit)
    if (page_limit is None or page_limit.get('basis') != 'enforced_limit'
            or type(page_limit.get('evidence')) is not str or not page_limit['evidence'].strip()):
        return None
    if limit is not None and (limit < current_pages or limit == 0):
        raise ValueError('page cap below current pages or zero')
    extra = _bound(companions)
    return None if limit is None or extra is None else page_size * limit + extra


def capacity(terms, allocations, free_by_pool, *, cap):
    """Conditional arithmetic, not proof authentication or operational admission.

    Input authors own complete coverage and independently justified bounds. B is
    the remaining *physical* payload allocation, H metadata and U transient peak.
    Map volumes to the real shared allocation pool before calling; duplicate F
    cannot be supplied as separate credits for one pool. No float rounding.

    known_budget subtotals retain justified terms of the selected budget
    expression, even when another term is missing. They are not lower bounds
    on actual disk demand when the supplied terms are upper bounds. Exceeding
    that budget does not demonstrate a shortage. Incomplete full totals and
    per-pool fits remain None; missing proof can never grant conditional_fit.
    """
    _number(cap)
    missing = []
    values = {}
    for name in ('P', 'D_B', 'D_S', 'M'):
        values[name] = _bound(terms.get(name))
        if values[name] is None:
            missing.append(name)
    logical_known = sum((2 if name == 'P' else 1) * value
                        for name, value in values.items() if value is not None)
    logical = None if missing else logical_known
    pools = {}
    for row in allocations:
        pool = row['pool']
        if type(pool) is not str or not pool:
            raise ValueError('allocation pool identity required')
        rec = pools.setdefault(pool, dict(allocation=0, threshold=None, fits=None,
                                          known_budget_bytes=0, known_budget_threshold=None))
        for name in ('B', 'H', 'U'):
            value = _bound(row.get(name))
            if value is None:
                missing.append(pool + ':' + name)
                rec['allocation'] = None
            else:
                rec['known_budget_bytes'] += value
                if rec['allocation'] is not None:
                    rec['allocation'] += value
    if not pools:
        missing.append('physical_scope')
    exceeds = logical_known > cap
    for pool, rec in pools.items():
        free = free_by_pool.get(pool)
        if free is None:
            missing.append(pool + ':free')
        else:
            _number(free)
        rec['known_budget_threshold'] = (6 * rec['known_budget_bytes'] + 4) // 5
        if free is not None and free < rec['known_budget_threshold']:
            exceeds = True
        if rec['allocation'] is not None:
            rec['threshold'] = (6 * rec['allocation'] + 4) // 5
            if free is not None:
                rec['fits'] = free >= rec['threshold']
    state = 'exceeds' if exceeds else 'unknown' if missing else 'conditional_fit'
    return dict(state=state, logical_bytes=logical, logical_known_budget_bytes=logical_known,
                pools=pools, missing=list(dict.fromkeys(missing)),
                scope='conditional_offline_arithmetic', runtime_acceptance=False)


def binding(required, facts, *, process, epoch):
    """Check a proposed loaded snapshot contract, without trusting its producer.

    process must encode host+PID+start identity, not bare reusable PID. A snapshot
    requires a supported, authorized producer; no such legacy producer is added
    here. Values may be private opaque IDs. Defaults/cwd/FDs are partial facts.
    """
    if not required or not process or not epoch:
        raise ValueError('nonempty binding scope required')
    covered = {}
    for fact in facts:
        if (fact.get('kind') == 'loaded_snapshot' and fact.get('process') == process
                and fact.get('epoch') == epoch and fact.get('complete') is True
                and type(fact.get('evidence')) is str and fact['evidence'].strip()
                and type(fact.get('value')) is str and fact['value']):
            covered.setdefault(fact['field'], set()).add(fact['value'])
    missing = [name for name in required if len(covered.get(name, set())) != 1]
    return dict(state='unknown' if missing else 'conditional_complete', missing=missing,
                runtime_acceptance=False)


def bounded_control(payload, cap):
    """Reject a serialized byte payload before releasing it to a future writer.

    Caller must enforce an aggregate ledger too. This is not a disk reservation,
    bounded serializer, log limiter, copy operation or permission to write.
    """
    _number(cap)
    if type(payload) is not bytes or len(payload) > cap:
        raise ValueError('serialized control cap exceeded or wrong type')
    return payload
