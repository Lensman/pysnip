try:
    import psyco
    psyco.full()
except ImportError:
    print '(optional: install psyco for optimizations)'