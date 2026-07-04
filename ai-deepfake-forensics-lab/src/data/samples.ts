/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { SampleMedia } from '../types';

export const STATIC_SAMPLES: SampleMedia[] = [
  {
    id: 'sample-politician',
    title: 'Senate Press Briefing Overlay',
    type: 'video',
    class: 'Fake',
    confidence: 94.6,
    risk: 'High',
    category: 'Political Broadcast',
    url: 'https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?auto=format&fit=crop&q=80&w=1000',
    findings: [
      'Frequent mouth geometry re-rendering and lip boundary micro-flickering (12Hz deviation)',
      'Artificial blink symmetry: Both eyelids move with extreme mechanical intervals (3.2 seconds uniform)',
      'Specular skin reflection vectors remain at 34° despite real studio keylight moving on the left',
      'Absent high-frequency camera-chip thermal noise; localized artificial smoothing profile'
    ],
    explanation: 'A deep temporal biomechanical analysis isolates specific lip-matching artifacts around phoneme boundaries. The subject\'s mouth boundaries exhibit rendering artifacts indicative of a 2D neural expression transfer. Furthermore, specular reflections are static, and iris structures show biometric degradation.',
    checkCirculating: 'Cryptographic hash search matches index DB-7393A: This video signature was highly active on major social networks starting March 14, 2026. Flagged as manipulated media payload.',
    overlays: [
      {
        id: 'p-1',
        type: 'anomaly',
        x: 41,
        y: 49,
        w: 18,
        h: 12,
        label: 'Oral Rendering Seam',
        description: 'Micro-fluctuations in edge contrast along the lips, typical of synthetic neural transfer models.'
      },
      {
        id: 'p-2',
        type: 'landmark',
        x: 44,
        y: 34,
        label: 'Asymmetric Gaze Check',
        description: 'Slightly divergent visual coordinates. Left eye reflection vector deviates by 8.4 degrees.'
      },
      {
        id: 'p-3',
        type: 'light_vector',
        x: 32,
        y: 42,
        label: 'Incident Vector Mismatch',
        description: 'Skin luminance registers a static 34° light angle. Studio lighting is positioned at 12°.'
      }
    ]
  },
  {
    id: 'sample-portrait',
    title: 'Synthetic Profile Portrait',
    type: 'image',
    class: 'Fake',
    confidence: 89.2,
    risk: 'Medium',
    category: 'Identity Profile',
    url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=1000',
    findings: [
      'Highly asymmetrical outer cartilage structure between the left and right ears',
      'Divergent pupillary light points: Specular highlights originate from contradictory coordinates',
      'Chaotic amorphous background noise: Texture rendering dissolves into fluid-like patterns',
      'Intermittent geometric artifacts along hair strands merging directly into negative space'
    ],
    explanation: 'The specimen displays several classic anomalies of StyleGAN or stable diffusion generative networks. While facial symmetry is exceptionally high (often indicating artificial origins), structural features such as ear design, pupil shape, and background textures contain severe logical incoherencies.',
    checkCirculating: 'Digital canvas footprint search did not find identical copies, but high-dimensional vector clusters associate this profile with automated bot accounts generated in early 2026.',
    overlays: [
      {
        id: 'por-1',
        type: 'landmark',
        x: 45,
        y: 38,
        label: 'Pupillary Irregularity',
        description: 'The right pupil shows a non-circular geometric outline under high-magnification edge tracing.'
      },
      {
        id: 'por-2',
        type: 'anomaly',
        x: 23,
        y: 53,
        label: 'Lobe Structural Void',
        description: 'Mismatched earlobe curves. Left ear exhibits an unformed lobe structure when mirrored.'
      },
      {
        id: 'por-3',
        type: 'anomaly',
        x: 82,
        y: 20,
        w: 15,
        h: 20,
        label: 'Amorphous Background Blur',
        description: 'Generator fails to resolve texturized details in background, resulting in fluid brush-like noise.'
      }
    ]
  },
  {
    id: 'sample-news',
    title: 'Mayor Jane Reed Broadcast',
    type: 'video',
    class: 'Real',
    confidence: 97.4,
    risk: 'Low',
    category: 'Official Archive',
    url: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=1000',
    findings: [
      'Sub-dermal tissue absorption correlates perfectly with light scattering across cheek contours',
      'Saccadic eye micro-movements and physiological blinks reflect natural neural regulation',
      'Continuous, uninterrupted sensor noise matches manufacturer specifications',
      'Oral cavity articulation exhibits flawless mechanical and acoustic synchronization'
    ],
    explanation: 'Forensic evaluation of this segment confirms authentic biological characteristics. Spatial light distribution maps correctly to the three-point lighting grid of the studio. Spectral noise evaluation shows consistent thermal sensor patterns without traces of post-processing, frame-swapping, or facial re-targeting.',
    checkCirculating: 'Verified Authentic. Cryptographic source signature matches city archive registered June 12, 2026. Certified original press record.',
    overlays: [
      {
        id: 'n-1',
        type: 'landmark',
        x: 45,
        y: 36,
        label: 'Physiological Blink Gaze',
        description: 'Exhibits typical biological gaze trajectory and organic saccades.'
      },
      {
        id: 'n-2',
        type: 'landmark',
        x: 50,
        y: 54,
        label: 'Volumetric Oral Trace',
        description: 'Teeth, tongue, and lip movements are physically natural with flawless acoustical sync.'
      },
      {
        id: 'n-3',
        type: 'landmark',
        x: 60,
        y: 42,
        label: 'Dynamic Light Match',
        description: 'Luminance correctly fluctuates with the ambient lighting shift across the cheekbones.'
      }
    ]
  },
  {
    id: 'sample-selfie',
    title: 'Selfie Blend Composite',
    type: 'image',
    class: 'Fake',
    confidence: 76.5,
    risk: 'Medium',
    category: 'Composite Media',
    url: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=1000',
    findings: [
      'Noticeable high-frequency contrast disparity along the collarline and lower throat area',
      'Shadow angles from nose features (facing left) contradict background tree shadows (facing right)',
      'Slight resolution mismatch: The facial region is 15% sharper than the surrounding ear and hair zones'
    ],
    explanation: 'Forensic testing indicates a composite "head swap." The facial features are extracted from a high-resolution source light grid and blended onto a secondary body template. A pronounced noise seam with blurring artifact lines is visible around the neck, demonstrating manual boundary patching.',
    checkCirculating: 'This face was matched to public professional profiles, but the clothing, location, and surrounding frame represent a novel composite with no pre-existing occurrences, indicating targeted face replacement.',
    overlays: [
      {
        id: 's-1',
        type: 'anomaly',
        x: 35,
        y: 72,
        w: 30,
        h: 5,
        label: 'Collarline Blending Seam',
        description: 'Abrupt step-down in background grain and sharpness along areolar neck boundaries.'
      },
      {
        id: 's-2',
        type: 'light_vector',
        x: 48,
        y: 48,
        label: 'Conflicting Shadow Origin',
        description: 'Calculated nose shadow suggests light from 45° left. Body/collar shadows fall forward.'
      }
    ]
  }
];
