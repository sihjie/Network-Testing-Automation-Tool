# Network-Testing-Automation-Tool
## Requirement:
1. Develop a command-line tool to test network stability for industrial switches.
2. ICMP PING Tests: Measure Round Trip Time (RTT) and packet loss for network
stability evaluation.
3. Support Multiple Target Devices: Allow users to input multiple IP addresses for
simultaneous testing.
4. Structured JSON Output:
    - Start and end timestamps.
    - RTT samples per device.
    - Packet loss percentage per device.
    - Configurable logging output format.
5. Error Handling & Logging:
    - Implement a retry mechanism (default: 3 retries before marking as
    unreachable).
    - Log test failures with timestamps and error details.
    - Allow configurable retry settings (e.g., --retry-count, --retry-interval).

## Implementation
1. 模組化：將邏輯封裝在 NetworkTester 類別裡，讓程式清晰且可維護。
2. 跨平台：根據作業系統（Windows / Unix-like）動態組合 ping 指令。
3. 多執行緒：同時測試多個 IP，避免一個目標阻塞整個流程。
4. 錯誤處理與重試：失敗時會自動重試，並記錄詳細日誌。
5. 結果輸出：用 JSON 包含開始與結束時間、各設備的 RTT 平均、最大值、部分樣本，以及封包遺失率。
6. `_single_ping`：負責單次 ping，加入重試與 timeout 保護，並有 debug 日誌方便除錯。
7. `_test_device`：針對單一設備在指定時間與速率下重複 ping，最後計算統計結果。

## Demo
<img width="894" height="505" alt="image" src="https://github.com/user-attachments/assets/0ce23444-9212-4972-a85f-c6c480d21bf7" />

