#include "ProxyWrapper.h"
#include <proxy.h>

extern "C" {

char** GetProxiesForURL(const char* url) try
{
    char** proxies = nullptr;
    auto proxyFactory = px_proxy_factory_new();
    if (proxyFactory != nullptr)
    {
        proxies = px_proxy_factory_get_proxies(proxyFactory, url);
        px_proxy_factory_free(proxyFactory);
    }
    return proxies;
}
catch (...)
{
    return nullptr;
}

} // extern "C"
