#!/bin/bash
cd "$(dirname "$0")/../frontend" && exec npm run dev -- --port 5173
