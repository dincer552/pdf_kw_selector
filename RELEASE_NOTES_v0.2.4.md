# PDF kW Selector v0.2.4

## CI regression fix

v0.2.3 reduced the CI failures to one remaining semantic extraction regression. v0.2.4 makes the fan-motor field detection explicit and regression-tested so `Supply Fan Motor Power 3 kW` is always classified as `fan_motor_power` before aggregate power fields.

The release keeps the existing Stage 1 behavior:

- motor rated power is the target field;
- Unit Total Power / capacity / shaft / VSD values are not used as motor power;
- Supply air -> Vantilatör;
- Return air / Exhaust air -> Aspiratör;
- 1x1 / 2x1 / 3x1 groups are expanded into physical motors.

## Build

Windows CI produces `PDF_KW_Selector_v0.2.4.exe` after all pytest tests pass.
