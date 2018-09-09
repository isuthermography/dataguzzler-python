all:
	python3 setup.py build

clean:
	rm -rf *.bak *~ core.* *.o *.pyc build/ dataguzzler_python.egg-info/ demos/*~ demos/*.bak demos/*.pyc dataguzzler_python/*~ dataguzzler_python/*.bak  dataguzzler_python/*.pyc dataguzzler_python/bin/*~ dataguzzler_python/bin/*.bak  dataguzzler_python/bin/*.pyc demos/__pycache__ dist/ __pycache__ dataguzzler_python/__pycache__

commit: clean
	hg addremove
	hg commit
