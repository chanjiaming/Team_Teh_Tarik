# Team_Teh_Tarik

1. download trace files from https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu/
2. python3 dpc2ram.py <input_file.xz> <output_file.trace> <request_limit (default: 15000000)>
3. modify the config_file
4. ./ramulator2 -f <config_file>
5. python3 ram2drampower.py <input_file_name.txt.ch0> <output_file.csv>
6. cd
7. ./cli -m ddr5.json -t <output_file.csv> -c ./DRAMPower/tests/tests_drampower/resources/cliconfig.json
