#include "Python.h"
#include <stdio.h>


static PyObject *decode_frame(PyObject *self, PyObject *args){
    PyRef module = PyImport_ImportModule("br24_driver");
    PyObject* moduleDict = PyModule_GetDict(module.Get());
    PyObject* protocolClass = PyDict_GetItemString(moduleDict, "br24");

    PyObject data_array, br24_decoder, seq;

    if (!PyArg_ParseTuple(args, "OO", &br24_decoder, &data_array))
        return NULL;
    

};

static PyMethodDef decoder_methods[] = {
        {"decode_frame", decode_frame, METH_VARARGS},
        {NULL, NULL}     /* Sentinel - marks the end of this structure */
};

void initsubgradient()  {
    (void) Py_InitModule("br24_frame_decoder", decoder_methods);
};

