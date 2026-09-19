# Native 2781 qualification

Source 2781f96bc19a433c36dc34d8ce560254cf08301a, CI 35299792272.
The first consumer failed because screen VBlank precedes the device's VBlank-IN
by one scanline. Normal fixture requests now wait for mapped SCU IST bit 0;
deliberate deadline probes retain their original offsets. The corrected consumer
exited zero: configuration, CD/cart/backup, 24 SCSP timer/divisor rates, six full
tap transport cases, scheduled partial-report save/load, four timeout cases,
H/V edge save restoration and four BIOS/background replay configurations.

This does not qualify sparse sockets, RESB, gameplay or complete hardware timing.
