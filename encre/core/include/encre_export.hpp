
#ifndef ENCRE_EXPORT_H
#define ENCRE_EXPORT_H

#ifdef ENCRE_STATIC_DEFINE
#  define ENCRE_EXPORT
#  define ENCRE_NO_EXPORT
#else
#  ifndef ENCRE_EXPORT
#    ifdef encre_EXPORTS
        /* We are building this library */
#      define ENCRE_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define ENCRE_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef ENCRE_NO_EXPORT
#    define ENCRE_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef ENCRE_DEPRECATED
#  define ENCRE_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef ENCRE_DEPRECATED_EXPORT
#  define ENCRE_DEPRECATED_EXPORT ENCRE_EXPORT ENCRE_DEPRECATED
#endif

#ifndef ENCRE_DEPRECATED_NO_EXPORT
#  define ENCRE_DEPRECATED_NO_EXPORT ENCRE_NO_EXPORT ENCRE_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef ENCRE_NO_DEPRECATED
#    define ENCRE_NO_DEPRECATED
#  endif
#endif

#endif /* ENCRE_EXPORT_H */
