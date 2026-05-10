(function(){
  var svg=document.querySelector('svg');
  var CH=28;
  var ol=document.createElementNS('http://www.w3.org/2000/svg','g');
  ol.setAttribute('pointer-events','none');
  svg.appendChild(ol);
  function mk(el){var y=+el.id.split('-')[2];return{el:el,y:y,p:el.parentNode,ns:el.nextSibling};}
  var cs=Array.from(document.querySelectorAll('[id^="sh-comp-"]')).map(mk).sort(function(a,b){return a.y-b.y;});
  var ks=Array.from(document.querySelectorAll('[id^="sh-conn-"]')).map(mk).sort(function(a,b){return a.y-b.y;});
  function sc(){return+svg.getAttribute('height')/svg.getBoundingClientRect().height;}
  function find(arr,thr){var r=null;for(var i=0;i<arr.length;i++){if(arr[i].y<=thr)r=arr[i];else break;}return r;}
  var pc=null,pk=null;
  function sqr(h){
    h.el.querySelectorAll('rect').forEach(function(r){
      var rx=r.getAttribute('rx');
      if(rx){r._rx=rx;r._ry=r.getAttribute('ry');r.removeAttribute('rx');r.removeAttribute('ry');}
    });
  }
  function unsqr(h){
    h.el.querySelectorAll('rect').forEach(function(r){
      if(r._rx){r.setAttribute('rx',r._rx);r.setAttribute('ry',r._ry);delete r._rx;delete r._ry;}
    });
  }
  function stick(h,dy){ol.appendChild(h.el);h.el.setAttribute('transform','translate(0,'+(dy-h.y)+')');sqr(h);}
  function unstick(h){
    unsqr(h);
    var ref=h.ns;
    if(ref&&ref.parentNode===h.p)h.p.insertBefore(h.el,ref);else h.p.appendChild(h.el);
    h.el.removeAttribute('transform');
  }
  function update(){
    var s=sc(),vt=window.scrollY*s;
    var ac=find(cs,vt),ak=find(ks,vt+CH);
    if(ac&&ak&&ak.y<=ac.y)ak=null;
    if(ac!==pc){if(pc)unstick(pc);pc=ac;}
    if(ak!==pk){if(pk)unstick(pk);pk=ak;}
    if(ac){
      var nc=cs[cs.indexOf(ac)+1];
      var cy=nc?Math.min(vt,nc.y-CH):vt;
      stick(ac,cy);
    }
    if(ak){
      var ki=ks.indexOf(ak),nk=ks[ki+1];
      var nc2=ac?cs[cs.indexOf(ac)+1]:null;
      var ny=Infinity;
      if(nk)ny=Math.min(ny,nk.y);
      if(nc2)ny=Math.min(ny,nc2.y);
      var ky=isFinite(ny)?Math.min(vt+CH,ny-CH):vt+CH;
      stick(ak,ky);
    }
  }
  window.addEventListener('scroll',update,{passive:true});
  window.addEventListener('resize',update,{passive:true});
  update();
})();
