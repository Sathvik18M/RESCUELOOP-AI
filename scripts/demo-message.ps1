param(
 [Parameter(Mandatory=$true)][ValidateSet('CONV001','CONV002','CONV003')][string]$Conversation,
 [Parameter(Mandatory=$true)][string]$Text,
 [string]$ApiUrl='http://127.0.0.1:8001',
 [string]$Token='local-rescueloop-demo'
)
$body = @{text=$Text;message_id=[guid]::NewGuid().ToString()} | ConvertTo-Json
$result = Invoke-RestMethod -Uri ($ApiUrl+'/api/demo/conversations/'+$Conversation+'/messages') -Method Post -Headers @{Authorization=('Bearer '+$Token)} -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
$result | ConvertTo-Json -Depth 5
