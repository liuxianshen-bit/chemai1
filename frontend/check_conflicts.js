const fs = require('fs');
const appJs = fs.readFileSync('app.js', 'utf8');
const teacherHtml = fs.readFileSync('teacher.html', 'utf8');
const studentHtml = fs.readFileSync('student.html', 'utf8');
const loginHtml = fs.readFileSync('login.html', 'utf8');

// 提取 app.js 顶层的 const/let/var/function 声明
const appDeclarations = new Set();
const regex = /^(?:const|let|var)\s+(\w+)|^function\s+(\w+)/gm;
let match;
while ((match = regex.exec(appJs)) !== null) {
    const name = match[1] || match[2];
    if (name) appDeclarations.add(name);
}

console.log('app.js 顶层声明 (' + appDeclarations.size + '):', [...appDeclarations].join(', '));

function checkConflicts(htmlContent, fileName) {
    const scriptMatches = htmlContent.match(/<script>([\s\S]*?)<\/script>/g);
    if (!scriptMatches) return;
    
    const conflicts = [];
    scriptMatches.forEach(script => {
        if (script.includes('src=')) return; // skip external scripts
        const content = script.replace(/<\/?script>/g, '');
        const innerRegex = /^\s*(?:const|let|var)\s+(\w+)|^\s*function\s+(\w+)/gm;
        let innerMatch;
        while ((innerMatch = innerRegex.exec(content)) !== null) {
            const name = innerMatch[1] || innerMatch[2];
            if (name && appDeclarations.has(name)) {
                conflicts.push(name);
            }
        }
    });
    
    if (conflicts.length > 0) {
        console.log('\n⚠️ CONFLICT in ' + fileName + ': ' + conflicts.join(', '));
    } else {
        console.log('\n✅ No conflicts in ' + fileName);
    }
}

checkConflicts(teacherHtml, 'teacher.html');
checkConflicts(studentHtml, 'student.html');
checkConflicts(loginHtml, 'login.html');
