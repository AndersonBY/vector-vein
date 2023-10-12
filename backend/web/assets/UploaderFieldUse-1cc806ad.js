import{c as o,A as y,aX as D,_ as F,$ as k,U as $,P as c,e as U,K as C,x as l,u,R as _,H as b,X as O}from"./index-52f19034.js";import{F as H}from"./FileOutlined-4973362b.js";var A={icon:{tag:"svg",attrs:{viewBox:"0 0 1024 1024",focusable:"false"},children:[{tag:"path",attrs:{d:"M885.2 446.3l-.2-.8-112.2-285.1c-5-16.1-19.9-27.2-36.8-27.2H281.2c-17 0-32.1 11.3-36.9 27.6L139.4 443l-.3.7-.2.8c-1.3 4.9-1.7 9.9-1 14.8-.1 1.6-.2 3.2-.2 4.8V830a60.9 60.9 0 0060.8 60.8h627.2c33.5 0 60.8-27.3 60.9-60.8V464.1c0-1.3 0-2.6-.1-3.7.4-4.9 0-9.6-1.3-14.1zm-295.8-43l-.3 15.7c-.8 44.9-31.8 75.1-77.1 75.1-22.1 0-41.1-7.1-54.8-20.6S436 441.2 435.6 419l-.3-15.7H229.5L309 210h399.2l81.7 193.3H589.4zm-375 76.8h157.3c24.3 57.1 76 90.8 140.4 90.8 33.7 0 65-9.4 90.3-27.2 22.2-15.6 39.5-37.4 50.7-63.6h156.5V814H214.4V480.1z"}}]},name:"inbox",theme:"outlined"};const B=A;function g(n){for(var t=1;t<arguments.length;t++){var e=arguments[t]!=null?Object(arguments[t]):{},a=Object.keys(e);typeof Object.getOwnPropertySymbols=="function"&&(a=a.concat(Object.getOwnPropertySymbols(e).filter(function(r){return Object.getOwnPropertyDescriptor(e,r).enumerable}))),a.forEach(function(r){N(n,r,e[r])})}return n}function N(n,t,e){return t in n?Object.defineProperty(n,t,{value:e,enumerable:!0,configurable:!0,writable:!0}):n[t]=e,n}var p=function(t,e){var a=g({},t,e.attrs);return o(y,g({},a,{icon:D}),null)};p.displayName="DeleteOutlined";p.inheritAttrs=!1;const z=p;function v(n){for(var t=1;t<arguments.length;t++){var e=arguments[t]!=null?Object(arguments[t]):{},a=Object.keys(e);typeof Object.getOwnPropertySymbols=="function"&&(a=a.concat(Object.getOwnPropertySymbols(e).filter(function(r){return Object.getOwnPropertyDescriptor(e,r).enumerable}))),a.forEach(function(r){E(n,r,e[r])})}return n}function E(n,t,e){return t in n?Object.defineProperty(n,t,{value:e,enumerable:!0,configurable:!0,writable:!0}):n[t]=e,n}var d=function(t,e){var a=v({},t,e.attrs);return o(y,v({},a,{icon:B}),null)};d.displayName="InboxOutlined";d.inheritAttrs=!1;const M=d,R={__name:"UploaderFieldUse",props:F({multiple:{type:Boolean,required:!1,default:!1}},{modelValue:{}}),emits:["update:modelValue"],setup(n){const t=n,e=k(n,"modelValue"),{t:a}=$(),r=s=>{const i=e.value.indexOf(s);e.value.splice(i,1)},h=async()=>{try{(await window.pywebview.api.open_file_dialog(t.multiple)).forEach(i=>{O.success(a("components.workspace.uploaderFieldUse.upload_success",{file:i})),e.value.push(i),!t.multiple&&e.value.length>1&&e.value.splice(0,1)})}catch(s){console.log(s),O.error(a("components.workspace.uploaderFieldUse.upload_failed"))}};return(s,i)=>{const x=c("a-button"),m=c("a-col"),w=c("a-typography-link"),P=c("a-typography-text"),S=c("a-list-item-meta"),I=c("a-list-item"),V=c("a-list"),j=c("a-row");return U(),C(j,{gutter:[16,16]},{default:l(()=>[o(m,{span:24},{default:l(()=>[o(x,{type:"primary",block:"",onClick:h},{icon:l(()=>[o(u(M))]),default:l(()=>[_(" "+b(u(a)("components.workspace.uploaderFieldUse.upload")),1)]),_:1})]),_:1}),o(m,{span:24},{default:l(()=>[o(V,{"data-source":e.value},{renderItem:l(({item:f})=>[o(I,null,{actions:l(()=>[o(w,{onClick:L=>r(f)},{default:l(()=>[o(u(z))]),_:2},1032,["onClick"])]),default:l(()=>[o(S,null,{title:l(()=>[o(P,null,{default:l(()=>[_(b(f),1)]),_:2},1024)]),avatar:l(()=>[o(u(H))]),_:2},1024)]),_:2},1024)]),_:1},8,["data-source"])]),_:1})]),_:1})}}};export{R as _};