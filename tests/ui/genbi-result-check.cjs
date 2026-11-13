// Synthetic finance fixtures. This test asserts visible feedback, not just HTTP success.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const base=process.env.MINIAPP_BASE||'http://localhost:8080';
const artifact=name=>path.resolve(__dirname,'../../logs',name);
const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow'}).format(new Date());
const currentStart=today.slice(0,7)+'-01';
const priorEnd=new Date(currentStart+'T12:00:00Z');priorEnd.setUTCDate(0);
const previousTo=priorEnd.toISOString().slice(0,10),previousFrom=previousTo.slice(0,7)+'-01';
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.PW_CHANNEL?{channel:process.env.PW_CHANNEL}:{})});
 try{
  const ctx=await browser.newContext({viewport:{width:390,height:700}}),page=await ctx.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://telegram.org/js/telegram-web-app.js',r=>r.fulfill({contentType:'application/javascript',body:`window.Telegram={WebApp:{initData:'fixture',colorScheme:'dark',ready(){},expand(){},onEvent(){},offEvent(){}}};`}));
  let reportCalls=0,requestedSpec=null;
  await page.route('**/api/v1/miniapp/**',async route=>{
   const path=new URL(route.request().url()).pathname.split('/miniapp')[1],body=route.request().postDataJSON();let data;
   if(path==='/bootstrap')data={accounts:[],assets:[],bot_username:'FinAI_sychikoff_bot'};
   else if(path==='/drafts')data=[];
   else if(path==='/reports'||path==='/query'){
    const querying=path==='/query';if(!querying)reportCalls++;
    const spec=querying?{...body.context,date_from:previousFrom,date_to:previousTo}:{...body,account_name:reportCalls===1?'Наличные':body.account_name};
    requestedSpec=spec;
    const rows=querying?[]:reportCalls===1?Array.from({length:30},(_,i)=>({label:'Категория '+(i+1),value:'15.00'})):[{label:'Продукты',value:'450.00'}];
    data={spec,title:'Расходы по категориям',currency:'RUB',series:[{key:'value',label:'Сумма'}],rows,totals:{value:querying?'0.00':'450.00'},explanation:'Synthetic fixture',empty:querying};
   }else data={cash:'0',cash_as_of:today,income:'0',living:'0',credit:'0',investment:'0',free:'0',recent:[],count:0};
   await route.fulfill({json:data});
  });
  await page.goto(base+'/miniapp');
  await page.getByRole('navigation').getByRole('button',{name:'Аналитика'}).click();
  await page.getByRole('button',{name:'Расходы по категориям',exact:true}).click();
  await page.getByLabel('Уточнить этот отчёт').fill('А за прошлый месяц?');
  await page.getByRole('button',{name:'Уточнить отчёт',exact:true}).click();
  await page.locator('#genbi-question').waitFor();
  await page.waitForFunction(()=>document.querySelector('#genbi-question').value==='');
  const position=await page.getByRole('heading',{name:'Расходы по категориям',exact:true}).boundingBox();
  const main=await page.locator('.mini-main').boundingBox();
  assert.ok(position.y>=main.y&&position.y+position.height<=main.y+main.height,'New result is above the visible scroll area: '+JSON.stringify(position));
  await page.getByText('А за прошлый месяц?',{exact:true}).waitFor();
  const result=page.getByRole('region',{name:'Результат отчёта'});
  assert.ok((await result.innerText()).includes('0 ₽'));
  assert.equal(await page.getByRole('button',{name:'Точные значения',exact:true}).count(),0);
  await page.screenshot({path:artifact('genbi-empty-result.png')});
  await page.getByRole('button',{name:'Показать текущий месяц',exact:true}).click();
  await page.getByText('Продукты',{exact:true}).waitFor();
  assert.equal(requestedSpec.date_from,currentStart);assert.equal(requestedSpec.date_to,today);assert.equal(requestedSpec.account_name,'Наличные');
  assert.ok((await result.innerText()).includes('450 ₽'));
  assert.deepEqual(errors,[]);
  await page.screenshot({path:artifact('genbi-current-result.png')});
  console.log(JSON.stringify({passed:true,resultVisible:true,questionVisible:true,emptyPeriodExplicit:true,currentMonthRecovery:true,accountPreserved:true,pageErrors:errors}));
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
