```
  _______ ______          __  __   _______ ______ _    _   _______       _____  _____ _  __  
 |__   __|  ____|   /\   |  \/  | |__   __|  ____| |  | | |__   __|/\   |  __ \|_   _| |/ /  
    | |  | |__     /  \  | \  / |    | |  | |__  | |__| |    | |  /  \  | |__) | | | | ' /   
    | |  |  __|   / /\ \ | |\/| |    | |  |  __| |  __  |    | | / /\ \ |  _  /  | | |  <    
    | |  | |____ / ____ \| |  | |    | |  | |____| |  | |    | |/ ____ \| | \ \ _| |_| . \   
    |_|  |______/_/    \_\_|  |_|    |_|  |______|_|  |_|    |_/_/    \_\_|  \_\_____|_|\_\
```
**Steps to build automated pipeline for the simulation of Multivariate Self-Adaptive Refreshing Time Selector for DRAM.**

1. **download target trace files from https://dpc3.compas.cs.stonybrook.edu/champsim-traces/index.html  
2. mkdir dram_pipeline && cd dram_pipeline  
3. mkdir trace_files  
4. **mv all your trace_files to trace_files directory  
5. git clone https://github.com/CMU-SAFARI/ramulator2  
6. cd ramulator2 && mkdir build && cd build && cmake .. -DCMAKE_POLICY_VERSION_MINIMUM=3.5 && make -j4 && cp ./ramulator2 ../ramulator2 && cd ..  
7. git clone https://github.com/tukl-msd/DRAMPower/tree/master  
8. cd DRAMPower && cmake -S . -B build -D DRAMPOWER_BUILD_CLI=Y && cmake --build build && cd ..  
9. git clone https://github.com/chanjiaming/Team_Teh_Tarik  
10. cd Team_Teh_Tarik  
11. mv ~/DDR5.cpp ~/ramulator2/src/dram/impl/DDR5.cpp  
12. mv ~/ddr5.json ~/DRAMPower/tests/tests_drampower/resources/ddr5.json
    
**Reference**
1.  “3rd data prefetching championship (DPC-3) trace suite,” Stony Brook University. [Online]. Available: https://dpc3.compas.cs.stonybrook.edu/champsim-traces/s
peccpu/
2. “SPEC CPU® 2017,” Spec.org, 2017. [Online]. Available: https://www.spec.org/cpu2017/
3. H. Luo, Y. C. Tugrul, F. N. Bostancı, A. Olgun, A. G. Yaglıkcı, and O. Mutlu, “Ramulator 2.0: A modern, modular, and extensible DRAM simulator,” 2023, arXiv:2308.11030. [Online]. Available: https://arxiv.org/abs/2308.11030
4. tukl-msd, “DRAMPower: Fast and accurate DRAM power and energy estimation tool,” GitHub, 2024. [Online]. Available: https://github.com/tukl-msd/DRAMPower


                                                                                           
                                                                                           
