#!/bin/sh
# Read-only integration regression. Requires the real App preview at loopback
# 5175 and the existing 2026-11-12 Gallery4446 record on Backend8001.
# Run via: sh scripts/check-gallery-modal-layout.sh (from frontend).
# Actual-App checks use real API/image bytes. The separate fixture route uses
# synthetic long content. Neither submits, reruns, exports or changes live data.
set -eu
ego-browser nodejs <<'BROWSER'
const assert = (await import('node:assert/strict')).default;
const task = await useOrCreateTaskSpace('AID-122 Gallery readability');
const results = [];
for (const scenario of [
  ...[1200, 800, 540, 1440].map(width=>({width,fixture:false})),
  ...[1200, 640, 540].map(width=>({width,fixture:true})),
]) {
  const {width,fixture} = scenario;
  await openOrReuseTab('http://127.0.0.1:5175/' +
    (fixture ? 'tests/gallery-modal-layout.html' : 'gallery'), {wait:true});
  await cdp('Emulation.setDeviceMetricsOverride', {width,height:850,deviceScaleFactor:1,mobile:false});
  await cdp('Page.reload', {ignoreCache:true});
  await waitForElement('input[type=date]', {timeout:15});
  if (!fixture) await js(String.raw`(() => {
    for(const el of document.querySelectorAll('input[type=date]')) {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'2026-11-12');
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.dispatchEvent(new Event('change',{bubbles:true}));
    }
  })()`);
  const card = fixture ? 'button:has(img)' : 'button:has(img[src*="1220a6f0"])';
  await waitForElement(card, {timeout:15});
  await click(card);
  await waitForElement('h3', {timeout:10});
  const geometry = await js(String.raw`(() => {
    const heading=document.querySelector('h3');
    const modal=heading.closest('div.overflow-auto');
    const box=modal.getBoundingClientRect();
    const left=box.left+modal.clientLeft, right=left+modal.clientWidth;
    const values=[...modal.querySelectorAll('dl dd')].map(el=>{
      const range=document.createRange(); range.selectNodeContents(el);
      return {label:el.previousElementSibling.textContent,text:el.textContent,
        fragments:[...range.getClientRects()].map(r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom}))};
    });
    const image=modal.querySelector('img'), imageBox=image.getBoundingClientRect();
    const paragraphs=[...modal.querySelectorAll('p')].map(el=>{
      const range=document.createRange(); range.selectNodeContents(el);
      return {label:'prompt',text:el.textContent,fragments:[...range.getClientRects()].map(r=>({left:r.left,right:r.right}))};
    });
    return {viewport:innerWidth,heading:heading.textContent,scrollLeft:modal.scrollLeft,
      clientWidth:modal.clientWidth,scrollWidth:modal.scrollWidth,clientHeight:modal.clientHeight,
      scrollHeight:modal.scrollHeight,left,right,top:box.top,bottom:box.bottom,
      image:{width:imageBox.width,height:imageBox.height,naturalWidth:image.naturalWidth,naturalHeight:image.naturalHeight},
      pageClientWidth:document.documentElement.clientWidth,pageScrollWidth:document.documentElement.scrollWidth,values,paragraphs};
  })()`);
  geometry.fixture=fixture;
  results.push(geometry); cliLog({...geometry,paragraphs:geometry.paragraphs.map(p=>({length:p.text.length,fragments:p.fragments.length}))});
  assert.equal(geometry.heading,'#4446');
  assert.equal(geometry.scrollLeft,0,'initial modal must not be horizontally scrolled');
  assert.equal(geometry.values.find(v=>v.label==='Seed: ').text,'1224040850519066617');
  assert.ok(geometry.scrollWidth<=geometry.clientWidth,'modal content must fit without horizontal navigation');
  assert.ok(geometry.pageScrollWidth<=geometry.pageClientWidth,'page must fit horizontally');
  if (fixture) assert.ok(geometry.scrollHeight>geometry.clientHeight,'long fixture must exercise vertical scrollbar');
  for (const value of [...geometry.values,...geometry.paragraphs]) for (const fragment of value.fragments) {
    assert.ok(fragment.left>=geometry.left-1 && fragment.right<=geometry.right+1,
      value.label+'text fragments must fit initial modal content area');
  }
  const seed=geometry.values.find(v=>v.label==='Seed: ');
  assert.ok(seed.fragments.every(r=>r.top>=geometry.top && r.bottom<=geometry.bottom),'entire seed must be visible initially');
  assert.ok(Math.abs(geometry.image.width/geometry.image.height-1.5)<0.01,'image must retain original aspect ratio');
  if (fixture) assert.equal(geometry.paragraphs[0].text,'Full prompt remains readable. '.repeat(220));
  await js(String.raw`(() => {const m=document.querySelector('h3').closest('div.overflow-auto');m.scrollTop=m.scrollHeight;})()`);
  const controls=await js(String.raw`(() => {const m=document.querySelector('h3').closest('div.overflow-auto');return [...m.querySelectorAll('button')].map(b=>({text:b.textContent,width:b.getBoundingClientRect().width}));})()`);
  assert.ok(controls.length>=4 && controls.every(b=>b.width>0),'action and close controls remain laid out');
  await click('xpath=//button[text()="關閉"]');
}
cliLog({passed:true,viewports:results.map(r=>r.viewport),taskId:task.id});
BROWSER
