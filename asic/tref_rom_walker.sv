module rf_rom_walker (
    input logic clk,
    input logic rst_n,
    input logic start,
   
    // Inputs (Scaled by 256)
    input logic [7:0] req_per_cycle, // sel = 1
    input logic [7:0] conflict_load, // sel = 2
    input logic [7:0] llc_miss, // sel = 3
    input logic [7:0] traffic_risk, // sel = 4
    input logic [7:0] rb_locality, // sel = 5
    input logic [7:0] rb_conflict, // sel = 6
   
    output logic [7:0] t_refi, // Prediction: 32, 48, or 64
    output logic done
);
    typedef struct packed {
        logic [2:0] sel;
        logic [7:0] threshold;
        logic [5:0] if_true;
        logic [5:0] if_false;
    } instr_t;
    // Sized to match 6-bit PC (0 to 63)
    instr_t rom [0:63];
    logic [5:0] pc;
   
    // Input Sample-and-Hold Registers
    logic [7:0] reg_req, reg_load, reg_miss, reg_risk, reg_local, reg_conf;
    initial begin
    for (int i = 0; i < 64; i++) begin
        rom[i] = '{3'd0, 8'd32, 6'd0, 6'd0};
    end
    rom[61] = '{3'd0, 8'd32, 6'd0, 6'd0}; // 32ms
    rom[62] = '{3'd0, 8'd48, 6'd0, 6'd0}; // 48ms
    rom[63] = '{3'd0, 8'd64, 6'd0, 6'd0}; // 64ms
    rom[0] = '{3'd1, 8'd7, 6'd1, 6'd2}; // Incoming_Req_Per_Cycle <= 0.0273
    rom[1] = '{3'd2, 8'd78, 6'd3, 6'd61}; // Conflict_Load <= 0.3047
    rom[2] = '{3'd2, 8'd5, 6'd61, 6'd15}; // Conflict_Load <= 0.0195
    rom[3] = '{3'd2, 8'd43, 6'd4, 6'd5}; // Conflict_Load <= 0.1680
    rom[4] = '{3'd3, 8'd4, 6'd6, 6'd7}; // LLC_Miss_Rate <= 0.0156
    rom[5] = '{3'd2, 8'd47, 6'd11, 6'd12}; // Conflict_Load <= 0.1836
    rom[6] = '{3'd3, 8'd1, 6'd63, 6'd8}; // LLC_Miss_Rate <= 0.0039
    rom[7] = '{3'd5, 8'd222, 6'd9, 6'd10}; // RB_Locality <= 0.8672
    rom[8] = '{3'd4, 8'd0, 6'd63, 6'd61}; // Traffic_Risk <= 0.0000
    rom[9] = '{3'd6, 8'd31, 6'd61, 6'd62}; // RB_Conflict_Rate <= 0.1211
    rom[10] = '{3'd1, 8'd1, 6'd62, 6'd63}; // Incoming_Req_Per_Cycle <= 0.0039
    rom[11] = '{3'd3, 8'd1, 6'd63, 6'd13}; // LLC_Miss_Rate <= 0.0039
    rom[12] = '{3'd1, 8'd2, 6'd14, 6'd63}; // Incoming_Req_Per_Cycle <= 0.0078
    rom[13] = '{3'd5, 8'd152, 6'd61, 6'd62}; // RB_Locality <= 0.5938
    rom[14] = '{3'd3, 8'd1, 6'd63, 6'd61}; // LLC_Miss_Rate <= 0.0039
    rom[15] = '{3'd6, 8'd7, 6'd16, 6'd62}; // RB_Conflict_Rate <= 0.0273
    rom[16] = '{3'd6, 8'd6, 6'd62, 6'd61}; // RB_Conflict_Rate <= 0.0234
end

    logic [7:0] mux_out;
    always_comb begin
        case (rom[pc].sel)
            3'd1: mux_out = reg_req;
            3'd2: mux_out = reg_load;
            3'd3: mux_out = reg_miss;
            3'd4: mux_out = reg_risk;
            3'd5: mux_out = reg_local;
            3'd6: mux_out = reg_conf;
            default: mux_out = 8'h00;
        endcase
    end
    typedef enum logic [1:0] {IDLE, WALK, DONE_STATE} state_t;
    state_t state;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            pc <= 0;
            t_refi <= 0;
            done <= 0;
            reg_req <= 0; reg_load <= 0; reg_miss <= 0;
            reg_risk <= 0; reg_local <= 0; reg_conf <= 0;
        end else begin
            case (state)
                IDLE: begin
                    done <= 0;
                    if (start) begin
                        // Sample inputs so they are stable during the walk
                        reg_req <= req_per_cycle;
                        reg_load <= conflict_load;
                        reg_miss <= llc_miss;
                        reg_risk <= traffic_risk;
                        reg_local <= rb_locality;
                        reg_conf <= rb_conflict;
                       
                        pc <= 0;
                        state <= WALK;
                    end
                end
                WALK: begin
                    if (rom[pc].sel == 3'd0) begin
                        t_refi <= rom[pc].threshold;
                        done <= 1'b1;
                        state <= DONE_STATE;
                    end else begin
                        if (mux_out <= rom[pc].threshold)
                            pc <= rom[pc].if_true;
                        else
                            pc <= rom[pc].if_false;
                    end
                end
                DONE_STATE: begin
                    if (!start) begin
                        done <= 1'b0;
                        state <= IDLE;
                    end
                end
               
                default: state <= IDLE;
            endcase
        end
    end
endmodule

`timescale 1ns / 1ps
module tb_rf_rom_walker();
    logic clk;
    logic rst_n;
    logic start;
   
    logic [7:0] req_per_cycle;
    logic [7:0] conflict_load;
    logic [7:0] llc_miss;
    logic [7:0] traffic_risk;
    logic [7:0] rb_locality;
    logic [7:0] rb_conflict;
   
    logic [7:0] t_refi;
    logic done;
    // Instantiate the DUT
    rf_rom_walker dut (.*);
    // 1ns Clock (1GHz)
    always #0.5 clk = ~clk;
    initial begin
        // Initialize
        clk = 0;
        rst_n = 0;
        start = 0;
        req_per_cycle = 0; conflict_load = 0; llc_miss = 0;
        traffic_risk = 0; rb_locality = 0; rb_conflict = 0;
        // Apply Reset
        #2 rst_n = 1;
        // TEST CASE 1: Path to 64ms (low req, low load, low miss)
        req_per_cycle = 8'd6; // <7
        conflict_load = 8'd40; // <43, <78
        llc_miss = 8'd0; // <1, <4
        traffic_risk = 8'd0; // irrelevant
        rb_locality = 8'd0;
        rb_conflict = 8'd0;
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST1: Expected 64, got %0d %s", t_refi, (t_refi==64) ? "PASS" : "FAIL");
        #10;
        // TEST CASE 2: Path to 32ms (high req, low load)
        req_per_cycle = 8'd8; // >7
        conflict_load = 8'd4; // <5
        llc_miss = 8'd0;
        traffic_risk = 8'd0;
        rb_locality = 8'd0;
        rb_conflict = 8'd0;
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST2: Expected 32, got %0d %s", t_refi, (t_refi==32) ? "PASS" : "FAIL");
        #10;
        // TEST CASE 3: Path to 48ms (high req, high load, low conf rate)
        req_per_cycle = 8'd8; // >7
        conflict_load = 8'd6; // >5
        llc_miss = 8'd0;
        traffic_risk = 8'd0;
        rb_locality = 8'd0;
        rb_conflict = 8'd5; // <6, <7
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST3: Expected 48, got %0d %s", t_refi, (t_refi==48) ? "PASS" : "FAIL");
        #10;
        // TEST CASE 4: Another 32ms path (high traffic risk in low branch)
        req_per_cycle = 8'd6; // <7
        conflict_load = 8'd40; // <43, <78
        llc_miss = 8'd2; // >1, <=4
        traffic_risk = 8'd1; // >0
        rb_locality = 8'd0;
        rb_conflict = 8'd0;
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST4: Expected 32, got %0d %s", t_refi, (t_refi==32) ? "PASS" : "FAIL");
        #10;
        // TEST CASE 5: 48ms path (high locality, low req in subbranch)
        req_per_cycle = 8'd0; // <1, <7
        conflict_load = 8'd40; // <43
        llc_miss = 8'd5; // >4
        traffic_risk = 8'd0;
        rb_locality = 8'd223; // >222
        rb_conflict = 8'd0;
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST5: Expected 48, got %0d %s", t_refi, (t_refi==48) ? "PASS" : "FAIL");
        #10 $stop;
    end
endmodule
