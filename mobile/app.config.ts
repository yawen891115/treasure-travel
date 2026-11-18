import type { ConfigContext, ExpoConfig } from 'expo/config';
export default ({ config }: ConfigContext): ExpoConfig => {
  const production = process.env.EAS_BUILD_PROFILE === 'production';
  const bundleIdentifier = process.env.IOS_BUNDLE_IDENTIFIER;
  if (production) {
    for (const key of ['EXPO_PUBLIC_API_URL', 'EXPO_PUBLIC_PRIVACY_URL']) {
      const value = process.env[key] || '';
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.hostname.endsWith('.example')) throw new Error(`${key} needs a real owned HTTPS URL.`);
    }
    if (!bundleIdentifier || !/^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/.test(bundleIdentifier)) throw new Error('Set your registered IOS_BUNDLE_IDENTIFIER.');
  }
  return { ...config, name: 'Treasure Travel', slug: 'treasure-travel', ios: { ...config.ios, ...(bundleIdentifier ? { bundleIdentifier } : {}) } };
};
