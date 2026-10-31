import { readFileSync } from "node:fs";

import ts from "typescript";

// 只执行页面中的请求声明与指定生命周期，避免复制生产算法或模拟无关界面。
export function executePageRequests<T>(
  url: URL,
  declarationNames: string[],
  dependencies: Record<string, unknown>,
  lifecycleNames: string[] = ["onBeforeUnmount"],
): T {
  const source = readFileSync(url, "utf8").match(/<script\b[^>]*>([\s\S]*?)<\/script>/)?.[1];
  if (!source) {
    throw new Error("页面缺少可执行的 script 区块。");
  }
  const parsed = ts.createSourceFile(url.pathname, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const selected = parsed.statements.filter((statement) => {
    if (ts.isFunctionDeclaration(statement)) {
      return statement.name && declarationNames.includes(statement.name.text);
    }
    if (ts.isVariableStatement(statement)) {
      return statement.declarationList.declarations.some((declaration) =>
        ts.isIdentifier(declaration.name) && declarationNames.includes(declaration.name.text),
      );
    }
    return ts.isExpressionStatement(statement)
      && ts.isCallExpression(statement.expression)
      && ts.isIdentifier(statement.expression.expression)
      && lifecycleNames.includes(statement.expression.expression.text);
  });
  const exportedNames = selected.flatMap((statement) => {
    if (ts.isFunctionDeclaration(statement)) {
      return statement.name ? [statement.name.text] : [];
    }
    if (ts.isVariableStatement(statement)) {
      return statement.declarationList.declarations.flatMap((declaration) =>
        ts.isIdentifier(declaration.name) ? [declaration.name.text] : [],
      );
    }
    return [];
  });
  const code = selected.map((statement) => statement.getText(parsed)).join("\n");
  const executable = ts.transpileModule(`${code}\nreturn { ${exportedNames.join(", ")} };`, {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
  }).outputText;
  return new Function(...Object.keys(dependencies), executable)(...Object.values(dependencies)) as T;
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}
