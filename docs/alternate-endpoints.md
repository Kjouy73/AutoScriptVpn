# Alternate connect endpoints ("bug host" / address pool)

Vortex-x can print multiple connection variants for the same user by changing only the connect address.
This is useful when you want to provide multiple stable endpoints that all route to the same server.

## Important

- The **connect address** must be a **domain/IP that points to your server**.
- Changing the connect address to a random third-party domain will not work unless it ultimately routes to your server.

## Manage endpoint list

Add endpoints:

```bash
vortex-x host add -a bug1.example.com
vortex-x host add -a bug2.example.com
```

List endpoints:

```bash
vortex-x host list
```

Remove endpoint:

```bash
vortex-x host remove -a bug1.example.com
```

## Print a user with alternate endpoints

When adding a user, Vortex-x will automatically print an **ALTERNATE ENDPOINTS** section if you have hosts configured.

You can also print a template link that contains `BUG_HOST` as a placeholder:

```bash
vortex-x user add -u alice -p vmess --print-template
```

The template is intended for clients that allow editing the server/address after import.
