# PDF Text Extraction Comparison: pypdf vs pymupdf

**Source directory:** `samples\lecture_note_test\raw`
**PDFs evaluated:** 11
**Pages per PDF (capped):** 3
**pypdf version:** evaluated via `pypdf.PdfReader`
**pymupdf version:** evaluated via `fitz.open().get_text()`

---

## Summary Metrics (averages across all PDFs)

| Metric | pypdf | pymupdf | Winner |
|---|---|---|---|
| Avg chars per file | 1018.0 | 1015.1 | pypdf |
| Avg non-ASCII ratio | 0.0 | 0.0 | pypdf |
| Avg mojibake patterns | 12.4 | 12.1 | pymupdf |
| Avg formula-like lines | 7.1 | 6.5 | pypdf |
| Avg control keyword matches | 14.5 | 14.5 | pypdf |

---

## Per-File Detail

### Chapter 6 digital Control1 2526 annotated.pdf (2553 KB)

#### pypdf
- chars: 953, lines: 32
- non-ASCII ratio: 0.0105
- mojibake patterns: 0
- formula-like lines: 5
- control keywords: 15

```
Chapter 6: Introduction to
digital control systems
Chapter 6: Introduction to digital control
• Basics and Implementation Issues
• Remaining Chapters
– Z-transforms of common signals and z-Transfer Functions
```

#### pymupdf
- chars: 956, lines: 54
- non-ASCII ratio: 0.0105
- mojibake patterns: 0
- formula-like lines: 5
- control keywords: 15

```
Chapter 6: Introduction to
digital control systems
Chapter 6: Introduction to digital control
•
Basics and Implementation Issues
• Remaining Chapters
```

---

### Chapter 8 Ztransform and Z TF 2526 annotated.pdf (2331 KB)

#### pypdf
- chars: 720, lines: 65
- non-ASCII ratio: 0.0500
- mojibake patterns: 3
- formula-like lines: 11
- control keywords: 13

```
Chapter 8: z-Transforms,
z Transfer Functions and
Block Diagrams
Chapter 8 z-transforms, z transfer function and Block Diagrams
Chapter 8 Overview:
• z-transform of common signals
```

#### pymupdf
- chars: 731, lines: 112
- non-ASCII ratio: 0.0492
- mojibake patterns: 2
- formula-like lines: 8
- control keywords: 13

```
Chapter 8: z-Transforms,
z Transfer Functions and
Block Diagrams
Chapter 8 z-transforms, z transfer function and Block Diagrams
Chapter 8 Overview:
• z-transform of common signals
```

---

### Chapter11  S-Zmapping 2526 annotated.pdf (1507 KB)

#### pypdf
- chars: 1343, lines: 54
- non-ASCII ratio: 0.1794
- mojibake patterns: 60
- formula-like lines: 23
- control keywords: 12

```
1
overview:
• S → Z Plane mapping: Poles on the s-plane are mapped to poles on
the z-plane;
• Concept of dominance in Z plane;
Chapter 11: Discrete Control Design
```

#### pymupdf
- chars: 1341, lines: 69
- non-ASCII ratio: 0.1797
- mojibake patterns: 60
- formula-like lines: 20
- control keywords: 12

```
1
overview:
• S →Z Plane mapping: Poles on the s-plane are mapped to poles on
the z-plane;
• Concept of dominance in Z plane;
Chapter 11: Discrete Control Design
```

---

### EEEE3066 Close loop Spec and Performance  UNNC 2526 annotated.pdf (1459 KB)

#### pypdf
- chars: 1410, lines: 55
- non-ASCII ratio: 0.1362
- mojibake patterns: 50
- formula-like lines: 13
- control keywords: 9

```
Chapter 2 :Closed Loop Specifications and Performance
 We wish the system output c(t) to follow r(t):
• With a particular speed (a particular decay rate: 𝜁𝜁𝜔𝜔𝑛𝑛)
• With a particular settling behaviour (a particular damping facotr 𝜁𝜁)
 Need CLTF to have dominant pair of
complex poles with desired 𝜔𝜔𝑛𝑛and 𝜁𝜁
```

#### pymupdf
- chars: 1395, lines: 61
- non-ASCII ratio: 0.1376
- mojibake patterns: 48
- formula-like lines: 12
- control keywords: 9

```
Chapter 2 :Closed Loop Specifications and Performance
We wish the system output c(t) to follow r(t):
• With a particular speed (a particular decay rate: 𝜁𝜁𝜔𝜔𝑛𝑛)
• With a particular settling behaviour (a particular damping facotr 𝜁𝜁)
Need CLTF to have dominant pair of
complex poles with desired 𝜔𝜔𝑛𝑛and 𝜁𝜁
```

---

### EEEE3066 Intro to Control System UNNC 2526 annotated.pdf (2132 KB)

#### pypdf
- chars: 949, lines: 28
- non-ASCII ratio: 0.0105
- mojibake patterns: 0
- formula-like lines: 3
- control keywords: 9

```
EEEE 3066 Control System Design
EEEE 3066 Control System Design
Prof. Jing Li,  EEE
Power Electronics, Machine and Control(PEMC) group
Provincial Key Laboratory of More Electric Aircraft Technology
Jing.li@Nottingham.edu.cn
```

#### pymupdf
- chars: 942, lines: 29
- non-ASCII ratio: 0.0106
- mojibake patterns: 0
- formula-like lines: 3
- control keywords: 9

```
EEEE 3066 Control System Design
EEEE 3066 Control System Design
Prof. Jing Li,  EEE
Power Electronics, Machine and Control(PEMC) group
Provincial Key Laboratory of More Electric Aircraft Technology
Jing.li@Nottingham.edu.cn
```

---

### EEEE3066 Intro to Control System UNNC 2526.pdf (1068 KB)

#### pypdf
- chars: 949, lines: 28
- non-ASCII ratio: 0.0105
- mojibake patterns: 0
- formula-like lines: 3
- control keywords: 9

```
EEEE 3066 Control System Design
EEEE 3066 Control System Design
Prof. Jing Li,  EEE
Power Electronics, Machine and Control(PEMC) group
Provincial Key Laboratory of More Electric Aircraft Technology
Jing.li@Nottingham.edu.cn
```

#### pymupdf
- chars: 942, lines: 29
- non-ASCII ratio: 0.0106
- mojibake patterns: 0
- formula-like lines: 3
- control keywords: 9

```
EEEE 3066 Control System Design
EEEE 3066 Control System Design
Prof. Jing Li,  EEE
Power Electronics, Machine and Control(PEMC) group
Provincial Key Laboratory of More Electric Aircraft Technology
Jing.li@Nottingham.edu.cn
```

---

### EEEE3066 Lectue4 S domain Control Design1 2526 blank.pdf (2428 KB)

#### pypdf
- chars: 1040, lines: 23
- non-ASCII ratio: 0.0663
- mojibake patterns: 16
- formula-like lines: 4
- control keywords: 20

```
Lecture 4:
S domain Controller
Design with RL method 1
Lecture 4: S domain controller design with root locus method 1
 Techniques for designing given type controllers using root
locus in S plane.
```

#### pymupdf
- chars: 1035, lines: 28
- non-ASCII ratio: 0.0667
- mojibake patterns: 16
- formula-like lines: 4
- control keywords: 20

```
Lecture 4:
S domain Controller
Design with RL method 1
Lecture 4: S domain controller design with root locus method 1

Techniques for designing given type controllers using root
```

---

### EEEE3066 Lecture 5 S domain Control Design2 2526annotated.pdf (4268 KB)

#### pypdf
- chars: 680, lines: 17
- non-ASCII ratio: 0.0088
- mojibake patterns: 0
- formula-like lines: 0
- control keywords: 17

```
Lecture 5:
S domain Control Design
with RL method 2
Lecture 5: S domain controller design with root locus method 2
5.1 Effect of Zeros on Closed Loop Response
▪ A Close Loop zero will contribute to an overshoot to the closed loop step response：
```

#### pymupdf
- chars: 681, lines: 22
- non-ASCII ratio: 0.0088
- mojibake patterns: 0
- formula-like lines: 0
- control keywords: 17

```
Lecture 5:
S domain Control Design
with RL method 2
Lecture 5: S domain controller design with root locus method 2
5.1 Effect of Zeros on Closed Loop Response
▪A Close Loop zero will contribute to an overshoot to the closed loop step response：
```

---

### EEEE3066 Lecture3 Root Locus method UNNC 2526 annotated.pdf (2446 KB)

#### pypdf
- chars: 819, lines: 33
- non-ASCII ratio: 0.0134
- mojibake patterns: 0
- formula-like lines: 2
- control keywords: 15

```
Chapter 3 : Root Locus Design Method
• understand what a root locus is and why it is important
• sketch a root locus for a given system
• use a root locus to determine gain of a controller
• use a root locus to predict behaviour of a closed loop system
• Learning Outcomes
```

#### pymupdf
- chars: 823, lines: 42
- non-ASCII ratio: 0.0134
- mojibake patterns: 0
- formula-like lines: 2
- control keywords: 15

```
Chapter 3 : Root Locus Design Method
• understand what a root locus is and why it is important
• sketch a root locus for a given system
• use a root locus to determine gain of a controller
• use a root locus to predict behaviour of a closed loop system
• Learning Outcomes
```

---

### EEEE3066 S domain Control Design1 2526 annotated.pdf (3945 KB)

#### pypdf
- chars: 1026, lines: 23
- non-ASCII ratio: 0.0409
- mojibake patterns: 7
- formula-like lines: 4
- control keywords: 20

```
Lecture 4:
S domain Controller
Design with RL method 1
Lecture 4: S domain controller design with root locus method 1
▪ Techniques for designing given type controllers using root
locus in S plane.
```

#### pymupdf
- chars: 1012, lines: 29
- non-ASCII ratio: 0.0415
- mojibake patterns: 7
- formula-like lines: 4
- control keywords: 20

```
Lecture 4:
S domain Controller
Design with RL method 1
Lecture 4: S domain controller design with root locus method 1
▪
Techniques for designing given type controllers using root
```

---

### Lecture 9 digital control design 2324blank.pdf (1593 KB)

#### pypdf
- chars: 1309, lines: 30
- non-ASCII ratio: 0.0099
- mojibake patterns: 0
- formula-like lines: 10
- control keywords: 20

```
Lecture 9: Digital Control Design
1
Chapter 11b: Digital Control Design
overview:
Be able to design PID(PI lead/Lag) type controllers in the discrete domain using root-locus
technique.
```

#### pymupdf
- chars: 1308, lines: 33
- non-ASCII ratio: 0.0099
- mojibake patterns: 0
- formula-like lines: 10
- control keywords: 20

```
Lecture 9: Digital Control Design
1
Chapter 11b: Digital Control Design
overview:
Be able to design PID(PI lead/Lag) type controllers in the discrete domain using root-locus
technique.
```

---

## Overall Assessment

- pypdf wins on 4 metric(s)
- pymupdf wins on 1 metric(s)

**Recommendation:** pypdf is adequate for this set of PDFs. No need to switch or add pymupdf as a dependency.

> **Note:** This evaluation covers text extraction quality only. OCR, image extraction, table detection, and annotation handling are not assessed. PyMuPDF offers richer features in those areas if needed in future.