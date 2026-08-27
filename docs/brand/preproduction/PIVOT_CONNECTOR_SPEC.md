# Biella Engine — Pivot and Connector Specification

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Purpose: define object origins, bearing pivots, connector relationships and deterministic mechanical assembly behavior

## 1. Principle

The Biella symbol must animate as a believable mechanism.

This document defines pivots by geometric relationships, not invented absolute coordinates. Exact coordinates are derived from the approved master geometry and final 3D construction once those sources exist.

No arbitrary world-origin rotation is acceptable.

## 2. Required independently controllable objects

Minimum object identities:

```text
LOGO_UPPER_BODY
LOGO_LOWER_BODY
CONNECTING_ROD
UPPER_BEARING
LOWER_BEARING
```

Where present, keep separately addressable:

```text
UPPER_INSERT
LOWER_INSERT
UPPER_EMISSIVE
LOWER_EMISSIVE
ROD_EMISSIVE_PATH
WORDMARK_BIELLA
WORDMARK_ENGINE
```

Optional mechanical details may be grouped logically, but must not block the required motion.

## 3. Coordinate convention

Use a consistent right-handed scene convention in the native DCC.

Recommended production convention:

```text
+Y = up
+X = logo horizontal/right
+Z = forward toward primary camera
```

If the DCC/exporter uses another native axis convention, preserve an explicit conversion at export. Do not silently rotate the authoritative source merely to satisfy an interchange format.

Assembled state local transforms should be deterministic and documented.

## 4. Master assembled state

Define one authoritative assembled transform state:

```text
ASSEMBLED
```

Requirements:

- upper and lower bodies on intended final axes;
- connecting rod endpoints centered on the two bearing centers;
- no visible interpenetration;
- no joint drift;
- approved silhouette matches master geometry;
- reset operation returns all mechanical objects to this exact state.

Store assembled transforms in source as one of:
- rest transforms;
- a named pose/action;
- a deterministic reset collection/script;
- equivalent native DCC mechanism.

## 5. Upper joint

### `UPPER_BEARING`

Pivot/origin:
- exact geometric center of upper bearing/joint;
- axis aligned with the actual bearing rotation axis;
- may not be placed at mesh bounding-box center if that differs from bearing center.

### `LOGO_UPPER_BODY`

Relationship:
- upper body may own or follow the upper bearing depending on final rig strategy;
- any parent/helper must preserve the actual bearing center as the effective articulation point.

### Connecting-rod upper endpoint

Define a stable connector/helper:

```text
CONNECTOR_ROD_UPPER
```

It must coincide with:
- the center of the upper rod eye;
- the upper bearing center in assembled state.

## 6. Lower joint

### `LOWER_BEARING`

Pivot/origin:
- exact geometric center of lower bearing/joint;
- rotation axis aligned with actual lower joint axis.

### `LOGO_LOWER_BODY`

Relationship:
- lower body may own/follow the lower bearing according to final rig;
- effective articulation remains centered on the lower bearing.

### Connecting-rod lower endpoint

Define:

```text
CONNECTOR_ROD_LOWER
```

It must coincide with:
- center of lower rod eye;
- lower bearing center in assembled state.

## 7. Connecting rod

Object:
```text
CONNECTING_ROD
```

Required helpers/connectors:

```text
CONNECTOR_ROD_UPPER
CONNECTOR_ROD_LOWER
```

Recommended origin:
- rod center of mass or lower joint center depending on final rig;
- origin choice must not prevent exact endpoint constraints.

Required behavior:
- rotates/translates as rigid metal;
- does not bend;
- maintains fixed distance between its two endpoint connector centers;
- can move from exploded to assembled state through transforms;
- can be constrained to bearing-center helpers without mesh drift.

## 8. Exploded state

Define one authored exploded pose:

```text
EXPLODED
```

Requirements:

- components are visually separated;
- every component retains a clear path to assembled state;
- exploded position must not alter mesh geometry;
- parent/constraint relationships remain valid or are intentionally blended;
- no part begins in a state that forces impossible intersection during assembly.

Exploded-state separation distances are composition-flexible and may vary by shot; assembled coordinates are not.

## 9. Mechanical lock state

Define a lock event/pose marker:

```text
MECHANICAL_LOCK
```

At this state:

- rod upper connector = upper bearing center;
- rod lower connector = lower bearing center;
- upper/lower bodies are on final axes;
- bearing seat is visually complete;
- no component slides through another;
- any compression/torque reaction is secondary animation around the correct pivots, not a geometry cheat.

## 10. Constraint strategy

Allowed:

- parent constraints;
- child-of constraints;
- point/position constraints;
- orientation constraints;
- IK-like mechanical constraints;
- custom driver relationships;
- equivalent DCC-native rig.

Required qualities:

- deterministic;
- editable;
- bakeable for interchange;
- reversible;
- no hidden dependency on temporary scene objects outside final source package.

## 11. Connector naming

Use exact helper names where helpers exist:

```text
PIVOT_UPPER_BEARING
PIVOT_LOWER_BEARING
CONNECTOR_ROD_UPPER
CONNECTOR_ROD_LOWER
CONNECTOR_UPPER_BODY
CONNECTOR_LOWER_BODY
```

Helpers may be empties/nulls/locators/bones according to DCC, but their semantic names remain stable.

## 12. Emission/FX attachment points

Provide optional stable attachment helpers:

```text
FX_UPPER_LOCK
FX_LOWER_LOCK
FX_ROD_PATH_START
FX_ROD_PATH_END
FX_SYMBOL_CENTER
```

FX helpers must follow the mechanism and must not determine mechanical geometry.

## 13. Camera-safe orientation

The primary front view must correspond to a stable world orientation so front/side/top cameras can be regenerated predictably.

Do not rotate the whole logo differently per render merely to fake a camera angle. Move the camera unless a shot explicitly calls for object rotation as motion.

## 14. Export behavior

For GLB/GLTF/FBX:

- bake animation/constraints when required by target;
- preserve object separation;
- preserve meaningful object names;
- preserve assembled pose;
- include animation only when the export is intended as a motion asset.

For OBJ:

- basic geometry compatibility only;
- no expectation of rig/pivot animation fidelity.

Native DCC remains authority for rig behavior.

## 15. Validation tests

PASS only when all are true:

1. upper bearing rotates around its real center;
2. lower bearing rotates around its real center;
3. connecting rod endpoints coincide with bearing centers in assembled state;
4. resetting returns exact assembled state;
5. exploded → aligned → lock motion uses transforms/constraints rather than mesh deformation;
6. no rigid part bends;
7. no visible mesh penetration occurs on approved path;
8. bearings do not drift;
9. helper/connector names are stable;
10. source reopens with rig relationships intact;
11. interchange export can reproduce the intended final assembled geometry;
12. final assembled frame matches approved master geometry.

## 16. Absolute-coordinate rule

Do not insert fabricated numeric XYZ coordinates in this specification.

Exact values become production evidence only after:

- approved `MASTER_LOGO_GEOMETRY.svg` exists;
- separated 3D objects are modeled from that geometry;
- bearing centers are measured from the actual source;
- the native scene is validated.

Those measured coordinates belong in source/QA evidence, not as guessed constants in this pre-production control.
