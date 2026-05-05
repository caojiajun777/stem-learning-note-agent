# RC Low-Pass Filter — Supplementary Notes

## Capacitor impedance

- The complex impedance of an ideal capacitor in sinusoidal steady-state is $Z_C = \frac{1}{j \omega C}$.
- Magnitude: $|Z_C| = \frac{1}{\omega C}$. Phase: $-90°$.
- Units: ohms (Ω). Capacitance is in farads (F); ω is in radians per second.

## Frequency-domain view

- Apply phasor voltage $V_{in}(j\omega)$ to the input.
- The output at the capacitor terminal is a divided voltage.
- The transfer function $H(j\omega) = V_{out}/V_{in}$ is dimensionless.

## Time constant

- $\tau = R C$ has units of seconds.
- It governs both step response (charging time) and frequency response (cutoff at $1/\tau$ rad/s).
- A small τ (small R or C) gives a fast circuit and a higher cutoff.

## Simplified derivation

- Voltage divider: $V_{out} = V_{in} \cdot \frac{1/(j \omega C)}{R + 1/(j \omega C)}$.
- Multiply numerator and denominator by $j \omega C$: $H(j\omega) = \frac{1}{1 + j \omega R C}$.
- Magnitude: $|H| = 1/\sqrt{1 + (\omega R C)^2}$.
- At $\omega R C = 1$, $|H| = 1/\sqrt{2}$ → that's the cutoff condition.
