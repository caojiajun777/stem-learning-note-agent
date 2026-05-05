# RC Low-Pass Filter — Examples

## Example 1: Compute cutoff frequency

Given $R = 10\,\text{k}\Omega$ and $C = 100\,\text{nF}$, find the cutoff frequency $f_c$.

Solution:
- $\tau = R C = 10^4 \cdot 10^{-7} = 10^{-3}\,\text{s}$.
- $f_c = 1/(2\pi \tau) \approx 159.15\,\text{Hz}$.
- Sanity check: a 1 kHz input is well above $f_c$ — expect significant attenuation.

## Example 2: Will a 5 kHz signal be attenuated?

For the same circuit ($f_c \approx 159\,\text{Hz}$), is a 5 kHz sinusoid significantly attenuated?

Solution:
- Ratio $f / f_c \approx 31.4$.
- Magnitude $|H| = 1/\sqrt{1 + 31.4^2} \approx 0.0318$.
- About −30 dB attenuation. Yes, strongly attenuated.

## Example 3: Choose R and C for a target cutoff

Design an RC low-pass with $f_c = 1\,\text{kHz}$. Pick R first.

Solution:
- Choose $R = 1\,\text{k}\Omega$.
- $C = 1/(2 \pi R f_c) = 1/(2 \pi \cdot 10^3 \cdot 10^3) \approx 159\,\text{nF}$.
- A standard 150 nF or 160 nF cap is a reasonable choice.
