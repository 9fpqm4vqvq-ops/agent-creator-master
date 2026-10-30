(function(root){
 'use strict';
 class TaskStore{
  constructor(storage){this.storage=storage;this.tasks=[];this.error='';try{const raw=storage.getItem('task-desk-v1');if(raw){const rows=JSON.parse(raw);if(!Array.isArray(rows))throw Error('Invalid data');this.tasks=rows.filter(t=>t&&typeof t.id==='string'&&typeof t.title==='string'&&t.title.length<=200&&typeof t.completed==='boolean');}}catch(e){this.error='Saved tasks could not be read. You can still work in this session.';}}
  persist(){try{this.storage.setItem('task-desk-v1',JSON.stringify(this.tasks));return true;}catch(e){this.error='Changes are available in this session, but could not be saved.';return false;}}
  add(value){const title=String(value).trim();if(!title||title.length>200)throw Error('Enter a task between 1 and 200 characters.');const task={id:globalThis.crypto?.randomUUID?.()||String(Date.now())+'-'+Math.random().toString(16).slice(2),title,completed:false};this.tasks.push(task);this.persist();return task;}
  toggle(id){const task=this.tasks.find(t=>t.id===id);if(!task)throw Error('Task not found.');task.completed=!task.completed;this.persist();}
  visible(filter='all'){if(!['all','active','completed'].includes(filter))throw Error('Invalid task filter.');return this.tasks.filter(t=>filter==='all'||(filter==='completed'?t.completed:!t.completed));}
 }
 function mount(document,storage){
  const store=new TaskStore(storage);let filter='all';const list=document.getElementById('tasks'),message=document.getElementById('message');
  function render(){list.replaceChildren();for(const task of store.visible(filter)){const li=document.createElement('li'),checkbox=document.createElement('input'),label=document.createElement('label');checkbox.type='checkbox';checkbox.id='task-'+task.id;checkbox.checked=task.completed;label.htmlFor=checkbox.id;label.textContent=task.title;li.dataset.completed=String(task.completed);checkbox.addEventListener('change',()=>{store.toggle(task.id);render();});li.append(checkbox,label);list.append(li);}document.getElementById('empty').hidden=store.visible(filter).length!==0;document.getElementById('counts').textContent=store.visible('active').length+' active · '+store.visible('completed').length+' completed';message.textContent=store.error;}
  document.getElementById('add-form').addEventListener('submit',event=>{event.preventDefault();const field=document.getElementById('task-title');try{store.add(field.value);field.value='';render();field.focus();}catch(e){message.textContent=e.message;}});
  for(const button of document.querySelectorAll('[data-filter]'))button.addEventListener('click',()=>{filter=button.dataset.filter;for(const b of document.querySelectorAll('[data-filter]'))b.setAttribute('aria-pressed',String(b===button));render();});
  render();return store;
 }
 if(typeof module!=='undefined')module.exports={TaskStore,mount};
 if(root.document){let storage;try{storage=root.localStorage;}catch(e){storage={getItem:()=>null,setItem:()=>{throw Error('Storage unavailable');}};}mount(root.document,storage);}
})(globalThis);
