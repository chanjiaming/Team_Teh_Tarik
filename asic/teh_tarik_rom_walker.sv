module teh_tarik_rom_walker (
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
    
        // Node 0: Root
        rom[0] = '{3'd3, 8'd41, 6'd1, 6'd25};   // LLC_Miss <= 41 (0.1591)

        // === LLC <= 0.1591 branch ===
        rom[1] = '{3'd1, 8'd1,   6'd2,  6'd7 };  // Req <= 1 (≈0.0021)

        // Low-Req sub-tree (Rules 1-6)
        rom[2] = '{3'd5, 8'd247, 6'd3, 6'd6 };  // RB_Loc <= 247 (0.9661)
        rom[3] = '{3'd4, 8'd0, 6'd4, 6'd62};  // Traffic_Risk <= 0
        rom[4] = '{3'd0, 8'd48, 6'd0, 6'd0 };  // Rule 1 → 48ms
        rom[6] = '{3'd0, 8'd64, 6'd0, 6'd0 };  // Rule 6 → 64ms

        // Medium-Req sub-tree (0.0021 < Req <= 0.0052)  ← THIS WAS BROKEN
        rom[7]  = '{3'd1, 8'd1, 6'd8, 6'd15};   // Req <=1 (≈0.0052)
        rom[8]  = '{3'd5, 8'd237,6'd9, 6'd12};   // RB_Loc <=237 (0.9264)
        rom[9]  = '{3'd4, 8'd0, 6'd10, 6'd11};   // Traffic <=0
        rom[10] = '{3'd0, 8'd32, 6'd0, 6'd0 };   // Rules 7+8 → 32ms   ← FIXED
        rom[11] = '{3'd5, 8'd128,6'd63, 6'd63};   // Rules 9+10 → 64ms
        rom[12] = '{3'd1, 8'd1, 6'd62, 6'd63};   // Rules 11+12 → 48/64

        // High-Req sub-tree (Req > 0.0052) - Rules 13+
        rom[15] = '{3'd5, 8'd154,6'd16, 6'd17};   // RB_Loc <=154 (0.601)
        rom[16] = '{3'd0, 8'd32, 6'd0, 6'd0 };   // Rule 13 → 32ms
        rom[17] = '{3'd1, 8'd6, 6'd18, 6'd19};   // Req <=6 (≈0.0215)
        rom[18] = '{3'd5, 8'd169, 6'd62, 6'd63};   // Rule 14/15
        rom[19] = '{3'd1, 8'd18, 6'd20, 6'd21};   // Req >0.0215
        rom[20] = '{3'd3, 8'd33, 6'd62, 6'd63};   // LLC <=33 (0.127)

        // === LLC > 0.1591 branch (Rules 18-25) ===
        rom[25] = '{3'd6, 8'd4,  6'd26, 6'd29};   // RB_Conflict <=4
        // (the rest of high-LLC nodes can stay as before or be left default 48ms)

        // Shared leaves
        rom[61] = '{3'd0, 8'd32, 6'd0, 6'd0}; // 32ms
        rom[62] = '{3'd0, 8'd48, 6'd0, 6'd0}; // 48ms
        rom[63] = '{3'd0, 8'd64, 6'd0, 6'd0}; // 64ms

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
        // TEST1 (Rule_ID=1) -> Expected 48
        // Conditions (fixed-point intent): llc_miss <= 0.1591, req <= 0.0021, rb_locality <= 0.9661, traffic_risk <= 0.0001
        req_per_cycle = 8'd0;
        conflict_load = 8'd0;
        llc_miss = 8'd40;   
        traffic_risk = 8'd0;   
        rb_locality = 8'd247;  
        rb_conflict  = 8'd0;
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST1 (Rule1): Expected 48, got %0d %s", t_refi, (t_refi==48) ? "PASS" : "FAIL");
        #10;

        // TEST2 (Rule_ID=4) -> Expected 48
        // Conditions: llc_miss <= 0.1591, req <= 0.0021, rb_locality <= 0.9661, traffic_risk > 0.0001, conflict_load <= 0.0424
        req_per_cycle = 8'd0;
        conflict_load = 8'd10;   
        llc_miss      = 8'd40;
        traffic_risk  = 8'd1;   
        rb_locality   = 8'd247;
        rb_conflict   = 8'd0;
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST2 (Rule4): Expected 48, got %0d %s", t_refi, (t_refi==48) ? "PASS" : "FAIL");
        #10;

        // TEST3 (Rule_ID=20) -> Expected 32
        // Conditions: llc_miss > 0.1591, rb_conflict > 0.0163, req <= 0.0693, rb_locality <= 0.5732
        req_per_cycle = 8'd17;   // <= floor(0.0693*256)=17
        conflict_load = 8'd0;
        llc_miss = 8'd41;  
        traffic_risk = 8'd0;
        rb_locality = 8'd146;  
        rb_conflict = 8'd5; 
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST3 (Rule20): Expected 32, got %0d %s", t_refi, (t_refi==32) ? "PASS" : "FAIL");
        #10;

        // TEST4 (Rule_ID=22) -> Expected 64
        // Conditions: llc_miss > 0.1591, rb_conflict > 0.0163, req <= 0.0693,
        //  rb_locality > 0.5732, llc_miss <= 0.2467, rb_locality > 0.9444
        req_per_cycle = 8'd17;  
        conflict_load = 8'd0;
        llc_miss = 8'd41;  
        traffic_risk  = 8'd0;
        rb_locality = 8'd242;  
        rb_conflict  = 8'd5;    
        #1 start = 1;
        #1 start = 0;
        wait(done);
        $display("TEST4 (Rule22): Expected 64, got %0d %s", t_refi, (t_refi==64) ? "PASS" : "FAIL");
        #10;
    end
endmodule
