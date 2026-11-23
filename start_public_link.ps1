# Starts a public link with a custom URL name for the orchestrator website.
# Requires Node.js LTS (winget install OpenJS.NodeJS.LTS).

$env:Path = 'C:\Program Files\nodejs;' + $env:Path
$subdomain = 'unified-test-orchestration'
$port = 8000

Write-Host "Starting public link: https://$subdomain.loca.lt -> http://127.0.0.1:$port"
& 'C:\Program Files\nodejs\npx.cmd' -y localtunnel --port $port --subdomain $subdomain
