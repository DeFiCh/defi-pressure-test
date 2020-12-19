#!/usr/bin/env python3

import logging as log
import toml

def must(ok, err):
    if not ok:
        raise Exception(err)

# exists does nothing, but exception will be raised before it's called if x doesn't exist
def exists(x):
    True

def checkRpcConfig(cfg):
    exists(cfg.Hostname)
    exists(cfg.Port)
    exists(cfg.User)
    exists(cfg.Password)

def checkDfiConfig(cfg):
    checkRpcConfig(cfg.RPC)

def checkConfig(cfg):
    checkDfiConfig(cfg.DFI)

class Config:
  '''The recursive class for building and representing objects with.'''
  def __init__(self, obj):
    for k, v in obj.items():
      if isinstance(v, dict):
        setattr(self, k, Config(v))
      else:
        setattr(self, k, v)
  def __getitem__(self, val):
    return self.__dict__[val]
  def __repr__(self):
    return '{%s}' % str(', '.join('%s : %s' % (k, repr(v)) for
      (k, v) in self.__dict__.items()))

# mustLoad load and check the anchor config, and exits on any error
def mustLoad(cfgPath):
    try:
        cfg = Config(toml.load(cfgPath))
        checkConfig(cfg)
    except KeyError as e:
        log.crit("%s: config field not found: %s" % (cfgPath, e))
    except AttributeError as e:
        log.crit("%s: config field not found: %s" % (cfgPath, e))
    except Exception as e:
        log.crit("%s parsing error: %s" % (cfgPath, e))
    return cfg
