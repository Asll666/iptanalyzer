import os
import pprint
import pickle

import capstone

import decoder
import windbgtool.debugger

class Analyzer:
    def __init__(self, cache_filename, pt_filename, dump_filename):
        self.PTFilename = pt_filename
        self.DumpFilename = dump_filename
        self.LoadedModules = {}
        self.AddressToSymbols = {}
        self.SymbolsToAddress = {}

        [self.BlockIPsToOffsets, self.BlockOffsetsToIPs] = pickle.load(open(cache_filename, "rb"))
        self.Debugger = windbgtool.debugger.DbgEngine()
        self.Debugger.LoadDump(dump_filename)
        self.Debugger.EnumerateModules()

    def DumpInstructions(self, start_offset, end_offset, instruction_offset):
        pytracer = decoder.PTLogAnalyzer(self.PTFilename, 
                                            self.DumpFilename, 
                                            dump_symbols = True,
                                            load_image = True,
                                            start_offset = start_offset, 
                                            end_offset = end_offset)

        for insn in pytracer.DecodeInstruction(move_forward = False, instruction_offset = instruction_offset):
            disasmline = pytracer.GetDisasmLine(insn)
            print('Instruction: %s' % (disasmline))

    def _NormalizeSymbol(self, symbol):
        (module, function) = symbol.split('!', 1)
        return module.lower() + '!' + function

    def DumpBlocks(self, cr3 = 0, start = 0, end = 0, dump_instructions = False):
        if not cr3 in self.BlockOffsetsToIPs:
            return

        offsets = list(self.BlockOffsetsToIPs[cr3].keys())            
        offsets.sort()

        for offset in offsets:
            for address_info in self.BlockOffsetsToIPs[cr3][offset]:
                address = address_info['IP']
                sync_offset = address_info['SyncOffset']

                if start > 0 and end > 0:
                    if address < start or end < address:
                        continue

                symbol = self.ResolveSymbol(address)
                print('> %.16x (%s) (sync_offset=%x, offset=%x)' % (address, symbol, sync_offset, offset))

    def DumpSymbolLocations(self, symbol, cr3 = 0, dump_instructions = False):
        symbol = self._NormalizeSymbol(symbol)
        if not symbol in self.SymbolsToAddress:
            print('Symbol [%s] is not found' % (symbol))
            return

        address = self.SymbolsToAddress[symbol]
        print('Searching %s: %x' % (symbol, address))

        if not cr3 in self.BlockIPsToOffsets:
            return

        if not address in self.BlockIPsToOffsets[cr3]:
            return

        for sync_offset in self.BlockIPsToOffsets[cr3][address]:
            for offset in self.BlockIPsToOffsets[cr3][address][sync_offset]:
                print('> sync_offset = %x / offset = %x' % (sync_offset, offset))

                if dump_instructions:
                    self.DumpInstructions(sync_offset, offset+2, offset)

    def FindOffsets(self, symbol):
        for block_address in self.BlockAddresses.keys():
            if block_address in self.AddressToSymbols:
                print(self.AddressToSymbols[block_address])

    def LoadModuleSymbols(self, module_name):
        module_name = module_name.split('.')[0]
        module_name = module_name.lower()
        if module_name in self.LoadedModules:
            return

        for (address, symbol) in self.Debugger.EnumerateModuleSymbols([module_name, ]).items():
            symbol = self._NormalizeSymbol(symbol)
            self.AddressToSymbols[address] = symbol
            self.SymbolsToAddress[symbol] = address

        self.LoadedModules[module_name] = True

    def LoadSymbols(self, address):
        address_info = self.Debugger.GetAddressInfo(address)
        if address_info and 'Module Name' in address_info:
            self.LoadModuleSymbols(address_info['Module Name'])

    def ResolveSymbols(self, cr3):
        for block_address in self.BlockIPsToOffsets[cr3].keys():
            self.LoadSymbols(block_address)

    def ResolveSymbol(self, address):
        if address in self.AddressToSymbols:
            symbol = self.AddressToSymbols[address]
        else:
            self.LoadSymbols(address)
            if address in self.AddressToSymbols:
                symbol = self.AddressToSymbols[address]
            else:
                symbol = ''
        return symbol
