# RC Low-Pass Filter

## What is an RC low-pass filter

- A simple frequency-selective circuit using one resistor R and one capacitor C.
- Passes low-frequency signals with little attenuation.
- Attenuates high-frequency signals.
- Used to smooth signals, reject high-frequency noise, and shape audio frequency response.

## Resistor and capacitor basics

- A resistor R limits current; the same instantaneous voltage relation applies for any frequency: $V = IR$.
- A capacitor stores charge; its impedance depends on frequency: $Z_C = 1/(j \omega C)$.
- At low frequency the capacitor looks like an open circuit (high impedance).
- At high frequency the capacitor looks like a short to ground (low impedance).

## Transfer function

- Treating the RC network as a voltage divider with $R$ on top and $1/(j \omega C)$ on bottom:
- $H(j\omega) = \frac{1}{1 + j \omega R C}$
- This is a first-order low-pass response.

## Cutoff frequency

- The cutoff frequency is where the magnitude drops by 3 dB (to $1/\sqrt{2}$).
- $f_c = \frac{1}{2 \pi R C}$
- Also written using time constant: $\tau = R C$.

## High and low frequency behaviour

- For $f \ll f_c$: output ≈ input. Phase shift small.
- For $f = f_c$: magnitude drops to about 0.707 of input. Phase ≈ −45°.
- For $f \gg f_c$: magnitude rolls off at −20 dB/decade. Phase approaches −90°.

## Bode plot intuition

- Magnitude plot: flat below cutoff, −20 dB/decade slope above.
- Use the corner frequency $f_c$ as the elbow of the asymptotic plot.
- The phase plot is a smooth curve from 0° to −90°.
