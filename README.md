# Push domain stats to InfluxDB

Configuration is done through the following environmental variables:

* `HIFI_DOMAIN_NAME='distributed2'`
* `export HIFI_SLEEP_INTERVAL=3`
* `export HIFI_DS_WEB_SESSION_UUID='deadbeef-dead-beef-dead-deadbeefdead'`

## The ds web session uuid

I wasn't able to setup basic auth or `ip_permissions` on an oauth protected
domain. I didn't exauste the debugging process on these to authentication
methods, but quickly gave up and switched to session ids. So, to run this
script you'll have to grab a session id.

## TODO

* [ ] better auth

