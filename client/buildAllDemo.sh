#!/bin/bash

cd demo_v13 && ncu -u && npm install && npm run build:prod && cd -
cd demo_v15 && ncu -u && npm install && npm run build:prod && cd -
cd demo_so-vits-svc_40 && ncu -u && npm install && npm run build:prod && cd -
cd demo_so-vits-svc_40_c && ncu -u && npm install && npm run build:prod && cd -
cd demo_so-vits-svc_40v2 && ncu -u && npm install && npm run build:prod && cd -
cd demo_so-vits-svc_40v2_c && ncu -u && npm install && npm run build:prod && cd -
cd demo_DDSP-SVC && ncu -u && npm install && npm run build:prod && cd -

