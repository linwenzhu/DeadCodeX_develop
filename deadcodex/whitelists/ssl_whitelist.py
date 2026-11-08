import ssl

ctx = ssl.SSLContext()
ctx.check_hostname
ctx.hostname_checks_common_name
getattr(ctx, "keylog_filename", None)
ctx.maximum_version
ctx.minimum_version
ctx.options
ctx.post_handshake_auth
ctx.sni_callback
ctx.sslobject_class
ctx.sslsocket_class
ctx.verify_flags
ctx.verify_mode
