const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use('/api', createProxyMiddleware({
    target: 'https://api.anthropic.com',
    changeOrigin: true,
    pathRewrite: { '^/api': '' },
    on: {
      proxyReq: (proxyReq) => {
        proxyReq.setHeader('x-api-key', 'YOUR_API_KEY_HERE');
        proxyReq.setHeader('anthropic-version', '2023-06-01');
      }
    }
  }));
};