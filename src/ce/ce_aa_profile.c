/* Minimal hooks for -finstrument-functions profiling of the guest decoder.
 * Timing is collected by the ARM fixture; these stubs keep the instrumented
 * calls resolvable in the freestanding PE image.
 */

void __cyg_profile_func_enter(void *this_fn, void *call_site)
{
    (void)this_fn;
    (void)call_site;
}

void __cyg_profile_func_exit(void *this_fn, void *call_site)
{
    (void)this_fn;
    (void)call_site;
}
