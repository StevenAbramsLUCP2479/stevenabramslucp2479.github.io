const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const context=await browser.newContext({viewport:{width:1280,height:1000}});
const page=await context.newPage();
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
async function login(username,password){
 await page.goto('http://127.0.0.1:8000/login/');
 await page.getByLabel('Username:').fill(username);
 await page.getByLabel('Password:').fill(password);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.waitForURL('http://127.0.0.1:8000/');
}
await login('browser-student','local-test-password-only');
await page.getByRole('link',{name:'Read instructions'}).click();
await page.screenshot({path:'quiz-instructions.png',fullPage:true});
await page.locator('#consent').check();
await page.getByRole('button',{name:'Start my attempt'}).click();
await page.getByText('Question 1 of 10', {exact:true}).waitFor();
assert.equal(await page.locator('input[type=radio]').count(),4);
await page.screenshot({path:'quiz-question.png',fullPage:true});
await page.locator('input[type=radio]').first().check();
await page.getByRole('button',{name:'Submit answer'}).click();
await page.getByText('Question 2 of 10', {exact:true}).waitFor();
// Leave the second question unanswered: server must advance with a timeout.
await page.getByText('Question 3 of 10', {exact:true}).waitFor({timeout:15000});
await page.evaluate(()=>window.dispatchEvent(new Event('blur')));
await page.getByRole('heading',{name:'Attempt locked'}).waitFor();
await page.reload();
await page.locator('#consent').check();
await page.getByRole('button',{name:'Start my attempt'}).click();
await page.getByRole('heading',{name:'Attempt locked'}).waitFor();
await page.getByRole('link',{name:'Return to my quizzes'}).click();
await page.getByRole('button',{name:'Sign out'}).click();
await login('browser-instructor','local-test-admin-only');
await page.getByRole('link',{name:'Instructor results'}).click();
const downloadPromise=page.waitForEvent('download');
await page.getByRole('link',{name:'Download results CSV'}).click();
const download=await downloadPromise;
assert.match(download.suggestedFilename(),/results.csv$/);
await page.goto('http://127.0.0.1:8000/admin/assessment/quiz/1/change/');
assert.equal(await page.locator('#id_seconds_per_question').inputValue(),'10');
assert.equal(await page.locator('#id_questions_to option').count(),100);
await page.screenshot({path:'quiz-admin.png',fullPage:true});
await page.setViewportSize({width:390,height:844});
await page.goto('http://127.0.0.1:8000/instructor/');
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
assert.deepEqual(errors,[]);
console.log('Browser flow passed: login, start, answer, timeout, focus lock, no restart, instructor CSV, admin bank widget, mobile layout.');
await browser.close();

})().catch(error => { console.error(error); process.exit(1); });
