#!/bin/bash
cd /home/integ/Important/PYTHON/project_summarization_service_fix/frontend
node node_modules/typescript/lib/tsc.js -b 2>&1
echo "TSC_EXIT_CODE: $?"
echo "---VITE---"
node node_modules/.bin/vite build 2>&1
echo "VITE_EXIT_CODE: $?"
