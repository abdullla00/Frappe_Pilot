import fs from 'fs';
import path from 'path';
import type { ProxyOptions } from 'vite';

interface CommonSiteConfig {
  webserver_port?: number;
  default_site?: string;
}

function getCommonSiteConfig(): CommonSiteConfig | null {
  let currentDir = path.resolve('.');
  while (currentDir !== '/') {
    if (
      fs.existsSync(path.join(currentDir, 'sites')) &&
      fs.existsSync(path.join(currentDir, 'apps'))
    ) {
      const configPath = path.join(currentDir, 'sites', 'common_site_config.json');
      if (fs.existsSync(configPath)) {
        return JSON.parse(fs.readFileSync(configPath, 'utf-8')) as CommonSiteConfig;
      }
      return null;
    }
    currentDir = path.resolve(currentDir, '..');
  }
  return null;
}

function detectFirstSite(): string | null {
  let currentDir = path.resolve('.');
  while (currentDir !== '/') {
    const sitesDir = path.join(currentDir, 'sites');
    if (fs.existsSync(sitesDir)) {
      const siteFolders = fs
        .readdirSync(sitesDir)
        .filter((folder: string) =>
          fs.existsSync(path.join(sitesDir, folder, 'site_config.json')),
        );
      if (siteFolders.length > 0) {
        return siteFolders[0];
      }
    }
    currentDir = path.resolve(currentDir, '..');
  }
  return null;
}

const config = getCommonSiteConfig();
const webserverPort = config?.webserver_port || 8000;
const siteName =
  process.env.FRAPPE_SITE || config?.default_site || detectFirstSite() || 'localhost';

const proxyOptions: Record<string, ProxyOptions> = {
  '^/(app|api|assets|files|private|login|pilot)(/.*)?': {
    target: `http://${siteName}:${webserverPort}`,
    changeOrigin: true,
    secure: false,
    ws: true,
  },
};

export default proxyOptions;
