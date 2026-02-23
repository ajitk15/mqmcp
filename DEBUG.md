curl -k -u mqreader:mqreader \
  -H "ibm-mq-rest-csrf-token: token" \
  -H "Content-Type: application/json" \
  -X POST "https://lodserver.company.com:9443/ibmmq/rest/v3/admin/action/qmgr/MYQMGR/mqsc" \
  -d '{"type": "runCommand", "parameters": {"command": "DISPLAY QLOCAL(*)"}}'
