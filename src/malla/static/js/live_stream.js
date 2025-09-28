(function(){
  try {
    const src = new EventSource('/stream/packets');
    src.addEventListener('ping', ()=>console.log('[live] ping'));
    src.onmessage = (e)=>{
      try {
        const data = JSON.parse(e.data);
        window.dispatchEvent(new CustomEvent('malla:live-packet', {detail: data}));
      } catch(err) {
        console.warn('live packet parse failed', err);
      }
    };
  } catch (e) {
    console.warn('EventSource unsupported', e);
  }
})();