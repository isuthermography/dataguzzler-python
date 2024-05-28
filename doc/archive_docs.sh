rm -rf build/
make latexpdf
make html
cd build
zip -r /tmp/dgpy_docs.zip latex/dataguzzler-python.pdf html/
