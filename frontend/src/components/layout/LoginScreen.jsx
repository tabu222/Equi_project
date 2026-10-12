import { useState } from 'react'

function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await onLogin(email.trim(), password)
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : 'Không thể đăng nhập.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel panel">
        <div className="brand-mark" aria-hidden="true">E</div>
        <p className="eyebrow">EQUITRACK</p>
        <h1>Đăng nhập</h1>
        <p>Đăng nhập bằng tài khoản câu lạc bộ để tiếp tục.</p>
        {error && <div className="alert-banner" role="alert">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label className="form-field"><span>Email</span><input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label className="form-field"><span>Mật khẩu</span><input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          <button className="button" type="submit" disabled={submitting}>{submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}</button>
        </form>
      </section>
    </main>
  )
}

export default LoginScreen
