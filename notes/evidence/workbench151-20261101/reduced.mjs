import {launch} from '../../../sim/web/test/launch.mjs';
const {browser}=await launch();
try {for(const locking of [true,false]){
const page=await browser.newPage();
await page.setContent('<fieldset><button>Play</button></fieldset>');
await page.evaluate(locking=>{
 const b=document.querySelector('button'),f=b.parentElement;
 window.events=[]; window.count=0;
 b.addEventListener('click',async()=>{count++;events.push('click');if(locking)f.disabled=true;await undefined;if(locking)f.disabled=false});
 for(const name of ['pointerdown','pointerup','mousedown','mouseup','click'])b.addEventListener(name,e=>events.push(name));
 setInterval(()=>{b.textContent=count%2?'Pause':'Play'},32);
},locking);
let lost=0;
for(let i=0;i<100;i++){
const before=await page.evaluate(()=>count);
await page.locator('button').click();
const after=await page.evaluate(()=>count);
if(after===before){lost++;console.log('lost',locking,i,await page.evaluate(()=>events.slice(-10)))}
}
console.log(JSON.stringify({locking,lost,count:await page.evaluate(()=>count)}));await page.close();
}}finally{await browser.close()}
