# Extra Caddy sites

One `*.caddy` file per additional site this VPS serves through the platform's
Caddy. Only this README is tracked; site files are created on the server.

The target service must be attached to the Docker network `core8-edge` and
should publish no host port. Example, `lead-agent.caddy`:

```
agent.example.com {
	encode zstd gzip
	reverse_proxy core8-lead-agent:4180
}
```

After adding or changing a file: `docker exec deploy-caddy-1 caddy reload --config /etc/caddy/Caddyfile`
