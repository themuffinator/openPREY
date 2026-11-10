/* Visual 1.19: position the wheel over a softly focused complete viewport.
   Source artwork stays in the wheel sheet; controls show the runtime fit rule. */
(() => {
  const sheet = document.getElementById('wheel'), source = document.getElementById('wheel2');
  if (!sheet || !source || document.getElementById('wheel-placement-preview')) return;
  const panel = document.createElement('div'); panel.className = 'demo';
  panel.innerHTML = `<h3>Wheel placement and scene focus</h3><p>The game keeps its original right-side position: <code>ui_weaponWheelOffset 27</code>. Zero centers it; negative values move left. Game settings exposes the same saved value. Narrow views fit the ring without changing the preference. An 8 dp Gaussian soft focus fades over the scene with the wheel, keeping the HUD, symbols and labels sharp.</p>
    <label>Horizontal offset <input id="wheel-placement-offset" type="range" min="-40" max="40" step="1" value="27"> <output id="wheel-placement-value">27%</output></label>
    <button id="wheel-placement-center">Center</button> <button id="wheel-placement-default">Default</button>
    <label>View <select id="wheel-placement-aspect"><option value="1.7777778">16:9</option><option value="3.5555556">32:9</option><option value="1.3333333">4:3</option><option value="0.5625">9:16</option></select></label>
    <label><input id="wheel-placement-focus" type="checkbox" checked> Scene soft focus</label>
    <svg id="wheel-placement-preview" role="img" aria-label="Weapon wheel in the full viewport" style="display:block;width:100%;max-height:440px;background:#151914;margin-top:12px"></svg>`;
  sheet.append(panel);
  const preview=panel.querySelector('svg'), offset=panel.querySelector('#wheel-placement-offset'), aspect=panel.querySelector('select'), focus=panel.querySelector('#wheel-placement-focus');
  function draw() {
    const width=720*Number(aspect.value), fit=Math.min(1,(width-32)/560), reach=Math.max(0,width/2-264*fit-16);
    const x=Math.max(-reach,Math.min(reach,width*Number(offset.value)/100));
    preview.setAttribute('viewBox',`${-width/2} -360 ${width} 720`);
    panel.querySelector('output').textContent=`${offset.value}%`;
    const art=window.__atlas.uniqueIds(source.innerHTML).replace(/<animate(?:Transform)?\b[\s\S]*?<\/animate(?:Transform)?>/g,'');
    // A vector corridor reference makes the scene-only focus visible without
    // shipping a retail screenshot. The wheel is a separate, unfiltered layer.
    preview.innerHTML=`<svg x="${-width/2}" y="-360" width="${width}" height="720" viewBox="0 0 1280 720" preserveAspectRatio="none"><defs><filter id="wheel-preview-gaussian" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="8"/></filter><linearGradient id="wheel-preview-light"><stop stop-color="#1D2924"/><stop offset=".5" stop-color="#657064"/><stop offset="1" stop-color="#17231F"/></linearGradient></defs><g ${focus.checked?'filter="url(#wheel-preview-gaussian)"':''}><path d="M0 0H1280V720H0Z" fill="url(#wheel-preview-light)"/><path d="M0 0L540 240H740L1280 0M0 720L540 480H740L1280 720M540 240V480M740 240V480M0 140L540 270M0 520L540 445M1280 140L740 270M1280 520L740 445" fill="none" stroke="#91A28C" stroke-width="6"/><path d="M575 265H705V480H575Z" fill="#16221D" stroke="#7C8979" stroke-width="4"/><path d="M64 300H290V415H64ZM990 300H1216V415H990Z" fill="#283A31" stroke="#829279" stroke-width="5"/><path d="M88 320H260M88 340H260M88 360H218M1014 320H1186M1014 340H1186M1014 360H1144" stroke="#B2BF9C" stroke-width="3"/></g></svg><path d="M-9 0H9M0-9V9" fill="none" stroke="#899578" stroke-opacity=".5"/><g transform="translate(${x} 0) scale(${fit})">${art}</g>`;
  }
  offset.addEventListener('input',draw); aspect.addEventListener('change',draw);
  focus.addEventListener('change',draw);
  panel.querySelector('#wheel-placement-center').onclick=()=>{offset.value=0;draw();};
  panel.querySelector('#wheel-placement-default').onclick=()=>{offset.value=27;draw();};
  // The source redraws when its family, roster or selection changes. Coalesce
  // those mutations; no additional permanent animation loop is introduced.
  let pending=false;
  new MutationObserver(()=>{if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;draw();});}}).observe(source,{childList:true,subtree:true});
  draw();
})();
