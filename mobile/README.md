# Treasure Travel iPhone app — development candidate

Native React Native/Expo screen, NOT a WebView wrapper. Implements trip requests, itinerary cards, native sharing, existing-account sign-in/out, explicit pre-connection disclosure, safe errors, loading/duplicate-request guards and session reset. No device-location permission, analytics SDK, payment flow, provider API key or password persistence. This build is **not submitted, signed, simulator-tested or App Store-ready**.

## Run

```
npm ci
cp .env.example .env
# Set an owned HTTPS backend and public privacy-policy URL.
npm run typecheck
npm test
npx expo start
```

Server must provide `/api/session`, `/api/login`, `/api/logout`, `/api/chat`, `/api/reset`. Client uses cookie session with `credentials: include`, an explicit CSRF token, and HTTPS origin Referer. Do not disable server CSRF checks to make native networking work. Cookies/native login persistence and logout must still be tested on a real iPhone. The current live backend is staff-only, so this app is an internal preview, not a public-user release. No account creation UI is implemented. Server session reset is NOT account deletion and NOT log erasure.

`EXPO_PUBLIC_*` values ship in the app. Never put Google/Anthropic keys there. All provider calls occur on the server. Only localhost HTTP is allowed in development code; production uses HTTPS without an ATS exception. No public endpoint or credentials are provisioned by these files. Native background/resume and network-loss behavior still require device QA. No requests are automatically retried, because a retry could incur duplicate paid provider usage.

## Release gates

1. Establish Apple Developer membership (currently USD 99/year; owner handles enrollment, identity and agreement/payment). Decide individual vs organization: individual seller uses legal personal name. Choose owned bundle identifier; it is deliberately not invented here.
2. Complete real backend/provider verification, live-date enforcement, attribution, consent and privacy retention/deletion policy, abuse protection and public-user authentication. Google-derived content needs correct Google attribution; do not display it on Apple Maps. No map view is included here. Display metadata/attribution contract still needs final backend integration before live release.
3. Replace template icon with approved original branding; add support URL, privacy-policy URL, screenshots, age rating, privacy labels and accurate review notes/demo account.
4. Build on macOS/Xcode or authorized Expo EAS service. Linux typecheck/JS export does NOT produce a signed iOS app. EAS cloud use may require an account/plan; no account, paid build or upload has been started.
5. Test native cookie/CSRF authentication, expired sessions, logout, reset, double-taps, cancellation, app backgrounding, poor networks, VoiceOver, Dynamic Type and small iPhone screens. Verify privacy policy and consent link are present in the production build.
6. If future version creates accounts, implement in-app account deletion. If third-party login is added, review Apple's login-equivalence rules. Review minimum-functionality requirements; acceptance is Apple's decision, never guaranteed.
7. Use TestFlight first, then explicitly submit for App Review. Uploading a build alone is not App Store approval/publication.

Official sources checked 2026-11-18:
- https://developer.apple.com/programs/enroll/
- https://developer.apple.com/app-store/review/guidelines/
- https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy
- https://docs.expo.dev/build/setup/
- https://docs.expo.dev/submit/ios/
- https://developers.google.com/maps/documentation/places/web-service/policies

## Verified in this Linux workspace

- TypeScript `tsc --noEmit`: pass.
- 8 API boundary/security unit tests: pass.
- Expo dependency compatibility check: pass.
- `expo export --platform ios`: generated Hermes JavaScript bundle, 597 modules, ~1.5 MB. This is NOT an `.ipa`, code signing, simulator or device verification.
- Production Expo configuration without owned HTTPS endpoints/registered bundle ID fails closed as intended.

Current chat contract requires `data_source` metadata. The UI displays Google attribution/live-vs-offline qualification, estimated costs, warnings and ephemeral live-turn behavior; share text retains warnings/source. Provider results remain in current React memory only. Google attribution styling and third-party attribution obligations still require final native UI review before public release.
