from distutils.core import setup, Extension

module1 =  Extension('br24_frame_decoder',sources = ['br24_frame_decoder_module.c'])

setup ( name = 'br24_frame_decoder',
        version = '0.1',
        description = 'Functions for decoding a frame from the BR24 radar',
        ext_modules = [module1])
