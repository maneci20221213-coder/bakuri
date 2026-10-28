def bootstrap():
    import sys
    try:import velopack
    except ImportError:
        if getattr(sys,'frozen',False):raise
        return
    # Never install a pending update merely because Windows started the app.
    def uninstall(*args):
        from windows import register_menu,set_startup
        register_menu(False);set_startup(False)
    app=velopack.App().set_auto_apply_on_startup(False)
    if sys.platform=='win32':app.on_before_uninstall_fast_callback(uninstall)
    app.run()

