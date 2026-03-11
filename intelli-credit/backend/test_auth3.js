import axios from 'axios';

async function test() {
  const email = 'login_test' + Date.now() + '@example.com';
  const password = 'realpassword123!';

  console.log("Signing up:", email);
  try {
    const signupRes = await axios.post('http://localhost:3001/api/auth/signup', { email, password });
    console.log("Signup success!");
  } catch (err) {
    console.error("Signup error:", err.response?.data || err.message);
    return;
  }

  console.log("\nLogging in:", email);
  try {
    const loginRes = await axios.post('http://localhost:3001/api/auth/login', { email, password });
    console.log("Login success!");
  } catch (err) {
    console.error("Login error:", err.response?.data || err.message);
  }
}

test();
